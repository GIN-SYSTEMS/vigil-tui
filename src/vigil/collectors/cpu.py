"""CPU package-power collector — AMD Ryzen focused.

Strategy waterfall (best → fallback):

Linux
    1. hwmon sysfs — k10temp / zenpower / amd_energy kernel driver.
       Reads power1_input (µW → W) and temp1_input (m°C → °C) from the
       same hwmon directory.
    2. RAPL powercap — energy_uj counter delta over elapsed time.
       Works on AMD (modern kernels) and Intel.  No temperature access.
    3. estimate — CPU% × configured TDP.  Always available.

Windows
    1. LibreHardwareMonitor WMI — requires LHM running as Administrator.
       Reads both Package power and CPU Package temperature.
    2. estimate — same CPU% fallback.

All strategies expose a ``read_temp()`` method.  Strategies that cannot
read temperature return 0.0 — the caller must treat 0.0 as "N/A."
"""

from __future__ import annotations

import logging
import platform
import time
from pathlib import Path
from typing import Optional

import psutil

from vigil import config
from vigil.collectors.base import Collector, SensorReading

log = logging.getLogger(__name__)

_SYSTEM = platform.system()

_AMD_HWMON_DRIVERS: frozenset[str] = frozenset({"k10temp", "zenpower", "amd_energy"})


# ── Public collector ───────────────────────────────────────────────────────

class CPUCollector(Collector):
    """Reads CPU package power and (where possible) die temperature."""

    def __init__(self) -> None:
        self._strategy: Collector = self._select_strategy()
        log.info("CPU collector strategy: %s", type(self._strategy).__name__)

    def read(self) -> SensorReading:
        return self._strategy.read()

    def read_temp(self) -> float:
        """Return CPU package temperature in °C, or 0.0 if unavailable."""
        if isinstance(self._strategy, (_HwmonStrategy, _WmiLhmStrategy)):
            try:
                return self._strategy.read_temp()
            except Exception:
                pass
        return 0.0

    def _select_strategy(self) -> Collector:
        if _SYSTEM == "Linux":
            return _try_hwmon() or _try_rapl() or _EstimateStrategy()
        if _SYSTEM == "Windows":
            return _try_wmi_lhm() or _EstimateStrategy()
        return _EstimateStrategy()


# ── Strategy implementations ───────────────────────────────────────────────

class _HwmonStrategy(Collector):
    """Read AMD hwmon power1_input (µW → W) and temp1_input (m°C → °C)."""

    def __init__(self, power_path: Path, temp_path: Optional[Path] = None) -> None:
        self._ppath = power_path
        self._tpath = temp_path

    def read(self) -> SensorReading:
        watts = int(self._ppath.read_text().strip()) / 1_000_000.0
        return SensorReading(watts, "hwmon", "CPU Package")

    def read_temp(self) -> float:
        if self._tpath is None:
            return 0.0
        return int(self._tpath.read_text().strip()) / 1_000.0


class _RaplStrategy(Collector):
    """CPU power from RAPL energy counter delta.  No temperature access."""

    def __init__(self, energy_path: Path) -> None:
        self._path = energy_path
        self._last_energy: Optional[int] = None
        self._last_ts: float = time.monotonic()
        self._max_energy: Optional[int] = self._read_max()

    def _read_max(self) -> Optional[int]:
        p = self._path.parent / "max_energy_range_uj"
        try:
            return int(p.read_text().strip())
        except Exception:
            return None

    def read(self) -> SensorReading:
        now = time.monotonic()
        current = int(self._path.read_text().strip())
        elapsed = now - self._last_ts

        if self._last_energy is None or elapsed < 0.05:
            self._last_energy = current
            self._last_ts = now
            return SensorReading(0.0, "rapl", "CPU Package (RAPL)")

        delta = current - self._last_energy
        if delta < 0 and self._max_energy is not None:
            delta += self._max_energy

        self._last_energy = current
        self._last_ts = now
        watts = max(0.0, (delta / 1_000_000.0) / elapsed)
        return SensorReading(watts, "rapl", "CPU Package (RAPL)")


class _WmiLhmStrategy(Collector):
    """Read CPU power and temperature from LibreHardwareMonitor WMI."""

    def __init__(self, conn: object) -> None:
        self._conn = conn

    def read(self) -> SensorReading:
        results = self._conn.query(  # type: ignore[attr-defined]
            "SELECT Value FROM Sensor "
            "WHERE SensorType='Power' AND Name LIKE '%Package%'"
        )
        if not results:
            raise RuntimeError("LHM CPU power sensor absent")
        return SensorReading(float(results[0].Value), "wmi", "CPU Package (LHM)")

    def read_temp(self) -> float:
        try:
            results = self._conn.query(  # type: ignore[attr-defined]
                "SELECT Value FROM Sensor "
                "WHERE SensorType='Temperature' AND Name LIKE '%Package%'"
            )
            if results:
                return float(results[0].Value)
        except Exception:
            pass
        return 0.0


class _EstimateStrategy(Collector):
    """Fallback: estimate watts from CPU% × TDP ceiling.  No temperature."""

    def read(self) -> SensorReading:
        pct = psutil.cpu_percent(interval=None)
        return SensorReading(
            (pct / 100.0) * config.CPU_TDP_WATTS,
            "estimate",
            "CPU Package (est.)",
            {"cpu_pct": round(pct, 1)},
        )


# ── Discovery helpers ──────────────────────────────────────────────────────

def _try_hwmon() -> Optional[_HwmonStrategy]:
    hwmon_root = Path("/sys/class/hwmon")
    if not hwmon_root.exists():
        return None

    for hwmon_dir in sorted(hwmon_root.iterdir()):
        name_file = hwmon_dir / "name"
        if not name_file.exists():
            continue
        try:
            driver = name_file.read_text().strip()
        except OSError:
            continue
        if driver not in _AMD_HWMON_DRIVERS:
            continue

        power_path = hwmon_dir / "power1_input"
        if not power_path.exists():
            continue
        try:
            power_path.read_text()   # permission probe
            temp_path = hwmon_dir / "temp1_input"
            log.info("AMD hwmon '%s' at %s", driver, hwmon_dir)
            return _HwmonStrategy(
                power_path,
                temp_path if temp_path.exists() else None,
            )
        except PermissionError:
            log.warning("hwmon at %s: permission denied", power_path)

    return None


def _try_rapl() -> Optional[_RaplStrategy]:
    rapl_root = Path("/sys/class/powercap")
    if not rapl_root.exists():
        return None

    for zone in ("amd-rapl:0", "intel-rapl:0", "intel-rapl", "amd-rapl"):
        energy = rapl_root / zone / "energy_uj"
        if not energy.exists():
            continue
        try:
            energy.read_text()
            log.info("RAPL counter at %s", energy)
            return _RaplStrategy(energy)
        except PermissionError:
            log.warning("RAPL at %s: permission denied", energy)

    return None


def _try_wmi_lhm() -> Optional[_WmiLhmStrategy]:
    try:
        import wmi  # type: ignore[import]

        conn = wmi.WMI(namespace=r"root\LibreHardwareMonitor")
        sensors = conn.query("SELECT Name FROM Sensor WHERE SensorType='Power'")
        if not sensors:
            log.debug("LHM WMI: no power sensors")
            return None
        log.info("LHM WMI: %d power sensor(s)", len(sensors))
        return _WmiLhmStrategy(conn)
    except Exception as exc:
        log.debug("LHM WMI unavailable: %s", exc)
        return None
