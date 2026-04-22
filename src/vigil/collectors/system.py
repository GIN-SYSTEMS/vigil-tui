"""System aggregator — assembles all sub-collector data into typed snapshots.

The key public type is ``SystemSnapshot``.  Every widget receives exactly
one SystemSnapshot per tick and unpacks only what it needs.

Snapshot types are plain dataclasses (slots=True for minimal overhead):
  CPUSnapshot  — wattage + temperature + per-core utilisation and frequency
  GPUSnapshot  — wattage + temperature + VRAM + fan + clocks + boost max
  RAMSnapshot  — wattage estimate + utilisation stats
  NetSnapshot  — network byte rates (from netdisk collector)
  DiskSnapshot — disk I/O byte rates (from netdisk collector)
  ProcessEntry — name / PID / CPU% / estimated wattage for one process
"""

from __future__ import annotations

import platform
import time
from dataclasses import dataclass, field
from typing import NamedTuple

import psutil

from vigil import config
from vigil.collectors.cpu import CPUCollector
from vigil.collectors.gpu import GPUCollector
from vigil.collectors.ram import RAMCollector
from vigil.collectors.netdisk import NetDiskCollector, NetSnapshot, DiskSnapshot

_SYSTEM = platform.system()


# ── Typed snapshot types ───────────────────────────────────────────────────

@dataclass(slots=True)
class CPUSnapshot:
    watts: float
    source: str
    label: str
    temp_c: float           # package temperature; 0.0 = unknown
    total_pct: float        # average across all logical cores (0–100)
    core_utils: list[float] # per logical core, 0–100
    core_mhz: list[float]   # per logical core frequency; may be empty
    max_mhz: float = 0.0    # boost max from psutil.cpu_freq().max


@dataclass(slots=True)
class GPUSnapshot:
    watts: float
    source: str
    name: str
    temp_c: float           # die temperature; 0 = unknown
    util_pct: int           # GPU compute utilisation, 0–100
    vram_used_mb: int
    vram_total_mb: int
    fan_pct: int            # 0–100; 0 = unavailable / passive cooling
    core_mhz: int           # graphics clock
    mem_mhz: int            # memory bus clock
    max_core_mhz: int = 0   # GPU boost max clock from NVML


@dataclass(slots=True)
class RAMSnapshot:
    watts: float
    used_gb: float
    total_gb: float
    percent: float          # 0–100


class ProcessEntry(NamedTuple):
    pid: int
    name: str
    cpu_pct: float          # psutil per-logical-core sum (may exceed 100)
    est_watts: float        # proportional share of CPU package power


@dataclass(slots=True)
class SystemSnapshot:
    cpu: CPUSnapshot
    gpu: GPUSnapshot
    ram: RAMSnapshot
    net: NetSnapshot
    disk: DiskSnapshot
    total_watts: float
    processes: list[ProcessEntry]
    timestamp: float = field(default_factory=time.monotonic)


# ── Collector orchestrator ─────────────────────────────────────────────────

class SystemCollector:
    """Calls all sub-collectors and assembles a SystemSnapshot each tick."""

    def __init__(self, process_filter: str | None = None) -> None:
        self._cpu = CPUCollector()
        self._gpu = GPUCollector()
        self._ram = RAMCollector()
        self._netdisk = NetDiskCollector()

        # --filter: case-insensitive substring applied in _top_processes.
        # Stored lower-cased so the tick-path comparison stays a plain `in`.
        # None or empty -> no filter.
        self._process_filter: str | None = (
            process_filter.strip().lower() if process_filter else None
        ) or None

        # Prime psutil CPU% counters (first call always returns 0.0).
        psutil.cpu_percent(interval=None)
        psutil.cpu_percent(percpu=True)
        for proc in psutil.process_iter(["cpu_percent"]):
            try:
                proc.cpu_percent(interval=None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    def collect(self) -> SystemSnapshot:
        # ── CPU ───────────────────────────────────────────────────────────
        cpu_r = self._cpu.safe_read()
        cpu_temp = self._cpu.read_temp()

        core_utils: list[float] = psutil.cpu_percent(percpu=True) or []  # type: ignore[assignment]
        total_pct = sum(core_utils) / max(len(core_utils), 1)

        core_mhz = self._per_core_mhz(len(core_utils))
        max_mhz = self._cpu_max_mhz()

        cpu = CPUSnapshot(
            watts=cpu_r.value,
            source=cpu_r.source,
            label=cpu_r.label,
            temp_c=cpu_temp,
            total_pct=round(total_pct, 1),
            core_utils=core_utils,
            core_mhz=core_mhz,
            max_mhz=max_mhz,
        )

        # ── GPU ───────────────────────────────────────────────────────────
        gpu_r = self._gpu.safe_read()
        ex = gpu_r.extra

        gpu = GPUSnapshot(
            watts=gpu_r.value,
            source=gpu_r.source,
            name=self._gpu.device_name,
            temp_c=float(ex.get("temp_c", 0)),
            util_pct=int(ex.get("gpu_util", 0)),
            vram_used_mb=int(ex.get("vram_used_mb", 0)),
            vram_total_mb=int(ex.get("vram_total_mb", 0)),
            fan_pct=int(ex.get("fan_pct", 0)),
            core_mhz=int(ex.get("core_mhz", 0)),
            mem_mhz=int(ex.get("mem_mhz", 0)),
            max_core_mhz=int(ex.get("max_core_mhz", 0)),
        )

        # ── RAM ───────────────────────────────────────────────────────────
        ram_r = self._ram.safe_read()
        rx = ram_r.extra

        ram = RAMSnapshot(
            watts=ram_r.value,
            used_gb=float(rx.get("used_gb", 0.0)),
            total_gb=float(rx.get("total_gb", 0.0)),
            percent=float(rx.get("percent", 0.0)),
        )

        # ── Net + Disk ────────────────────────────────────────────────────
        net, disk = self._netdisk.collect()

        total = cpu.watts + gpu.watts + ram.watts

        return SystemSnapshot(
            cpu=cpu,
            gpu=gpu,
            ram=ram,
            net=net,
            disk=disk,
            total_watts=total,
            processes=self._top_processes(cpu.watts),
        )

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _per_core_mhz(num_cores: int) -> list[float]:
        """Return per-core MHz list; falls back to overall freq if percpu fails."""
        try:
            freqs = psutil.cpu_freq(percpu=True)
            if freqs and len(freqs) == num_cores:
                return [f.current for f in freqs]
        except Exception:
            pass

        try:
            overall = psutil.cpu_freq()
            if overall:
                return [overall.current] * num_cores
        except Exception:
            pass

        return []

    @staticmethod
    def _cpu_max_mhz() -> float:
        """Return the CPU's advertised boost max from psutil.cpu_freq()."""
        try:
            freq = psutil.cpu_freq()
            if freq and freq.max > 0:
                return freq.max
        except Exception:
            pass
        return 0.0

    @staticmethod
    def _should_filter(name: str) -> bool:
        lower = name.lower()
        if lower in config.PROCESS_FILTER_NAMES:
            return True
        return any(lower.startswith(p) for p in config.PROCESS_FILTER_PREFIXES)

    def _top_processes(self, cpu_watts: float) -> list[ProcessEntry]:
        logical_cores = psutil.cpu_count(logical=True) or 1
        entries: list[ProcessEntry] = []

        try:
            for proc in psutil.process_iter(["pid", "name", "cpu_percent"]):
                try:
                    info = proc.info
                    name: str = (info.get("name") or "?").strip()
                    if self._should_filter(name):
                        continue
                    if (
                        self._process_filter is not None
                        and self._process_filter not in name.lower()
                    ):
                        continue
                    pct: float = info.get("cpu_percent") or 0.0
                    if pct < 0.1:
                        continue
                    share = min(pct / (logical_cores * 100.0), 1.0)
                    entries.append(ProcessEntry(
                        pid=info["pid"],
                        name=name[:22],
                        cpu_pct=round(pct, 1),
                        est_watts=round(share * cpu_watts, 2),
                    ))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass

        entries.sort(key=lambda e: e.est_watts, reverse=True)
        return entries[: config.PROCESS_TOP_N]
