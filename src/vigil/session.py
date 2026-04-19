"""Session state — cost accumulation, baseline delta, throttle, alerts, logging.

SessionState is updated once per tick from the async app._tick().
All I/O (webhook POST, JSONL write) is fire-and-forget via asyncio.create_task()
so the UI event loop is never blocked.
"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from vigil.collectors.system import CPUSnapshot, GPUSnapshot, SystemSnapshot
from vigil.config_manager import AppConfig


# ── Efficiency helpers ─────────────────────────────────────────────────────

def calc_cpu_efficiency(snap: CPUSnapshot, tdp: float) -> float:
    """Performance-per-watt ratio. 1.0 = perfectly efficient at TDP."""
    if snap.watts <= 0 or tdp <= 0:
        return 0.0
    util = snap.total_pct / 100.0
    load_frac = snap.watts / tdp
    return util / max(load_frac, 0.01)


def calc_gpu_efficiency(snap: GPUSnapshot, tdp: float) -> float:
    if snap.watts <= 0 or tdp <= 0:
        return 0.0
    util = snap.util_pct / 100.0
    load_frac = snap.watts / tdp
    return util / max(load_frac, 0.01)


def efficiency_label(score: float) -> tuple[str, str]:
    """Return (label, color) for an efficiency score."""
    if score >= 0.90:
        return "OPTIMAL", "#00ccaa"
    if score >= 0.70:
        return "NORMAL", "#6a7a8a"
    if score >= 0.45:
        return "LOW EFF", "#cc8800"
    return "THROTTLE", "#cc4400"


# ── Throttle detection ────────────────────────────────────────────────────

def cpu_throttle_ratio(snap: CPUSnapshot) -> float:
    """avg_mhz / max_mhz; 1.0 = full boost, < 0.80 = throttling."""
    if not snap.core_mhz or snap.max_mhz <= 0:
        return 1.0
    avg = sum(snap.core_mhz) / len(snap.core_mhz)
    return avg / snap.max_mhz


def gpu_throttle_ratio(snap: GPUSnapshot) -> float:
    if snap.max_core_mhz <= 0 or snap.core_mhz <= 0:
        return 1.0
    return snap.core_mhz / snap.max_core_mhz


# ── Log directory ─────────────────────────────────────────────────────────

_LOG_DIR = Path.home() / ".local" / "share" / "vigil"


def _log_path() -> Path:
    today = time.strftime("%Y-%m-%d")
    return _LOG_DIR / f"{today}.jsonl"


def log_snapshot_sync(snap: SystemSnapshot, session_kwh: float) -> None:
    """Append one JSONL record synchronously (call from asyncio.to_thread)."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": snap.timestamp,
        "cpu_w": round(snap.cpu.watts, 2),
        "cpu_pct": round(snap.cpu.total_pct, 1),
        "cpu_temp": round(snap.cpu.temp_c, 1),
        "gpu_w": round(snap.gpu.watts, 2),
        "gpu_pct": snap.gpu.util_pct,
        "gpu_temp": snap.gpu.temp_c,
        "ram_pct": round(snap.ram.percent, 1),
        "total_w": round(snap.total_watts, 2),
        "session_kwh": round(session_kwh, 6),
    }
    with _log_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


# ── Webhook ───────────────────────────────────────────────────────────────

async def _post_webhook(url: str, payload: dict) -> None:
    body = json.dumps(payload).encode()
    try:
        await asyncio.to_thread(
            lambda: urllib.request.urlopen(
                urllib.request.Request(
                    url,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                ),
                timeout=5,
            )
        )
    except Exception:
        pass


# ── Session state ─────────────────────────────────────────────────────────

@dataclass
class BaselineSnapshot:
    cpu_watts: float
    gpu_watts: float
    ram_watts: float
    cpu_temp: float
    total_watts: float


@dataclass
class SessionState:
    cfg: AppConfig
    log_enabled: bool = False

    # Accumulated energy
    _accumulated_kwh: float = field(default=0.0, repr=False)
    _session_start: float = field(default_factory=time.monotonic, repr=False)

    # Baseline
    baseline: Optional[BaselineSnapshot] = field(default=None, repr=False)

    # Alert debounce — don't spam; once per 5 min per alert type
    _last_alert_cpu_temp: float = field(default=0.0, repr=False)
    _last_alert_cpu_watt: float = field(default=0.0, repr=False)
    _alert_cooldown: float = field(default=300.0, repr=False)

    def tick(self, snap: SystemSnapshot, interval: float) -> None:
        """Call once per update from the async tick handler."""
        self._accumulated_kwh += (snap.total_watts / 1_000.0) * (interval / 3_600.0)

        if self.log_enabled:
            asyncio.create_task(
                asyncio.to_thread(log_snapshot_sync, snap, self._accumulated_kwh)
            )

    def set_baseline(self, snap: SystemSnapshot) -> None:
        self.baseline = BaselineSnapshot(
            cpu_watts=snap.cpu.watts,
            gpu_watts=snap.gpu.watts,
            ram_watts=snap.ram.watts,
            cpu_temp=snap.cpu.temp_c,
            total_watts=snap.total_watts,
        )

    def clear_baseline(self) -> None:
        self.baseline = None

    # ── Cost helpers ──────────────────────────────────────────────────────

    def session_cost(self) -> float:
        return self._accumulated_kwh * self.cfg.kwh_price

    def cost_per_hour(self, current_watts: float) -> float:
        return (current_watts / 1_000.0) * self.cfg.kwh_price

    def cost_per_day(self, current_watts: float) -> float:
        return self.cost_per_hour(current_watts) * 24.0

    def session_duration_s(self) -> float:
        return time.monotonic() - self._session_start

    # ── Alerts ────────────────────────────────────────────────────────────

    async def check_and_alert(self, snap: SystemSnapshot) -> None:
        url = self.cfg.webhook_url
        if not url:
            return

        now = time.monotonic()
        triggered: list[dict] = []

        if snap.cpu.temp_c >= self.cfg.cpu_temp_thresh:
            if now - self._last_alert_cpu_temp > self._alert_cooldown:
                self._last_alert_cpu_temp = now
                triggered.append({
                    "alert": "cpu_temp",
                    "value": snap.cpu.temp_c,
                    "threshold": self.cfg.cpu_temp_thresh,
                })

        cpu_tdp_pct = (snap.cpu.watts / max(self.cfg.cpu_tdp_watts, 1.0)) * 100.0
        if cpu_tdp_pct >= self.cfg.cpu_watt_thresh_pct:
            if now - self._last_alert_cpu_watt > self._alert_cooldown:
                self._last_alert_cpu_watt = now
                triggered.append({
                    "alert": "cpu_power",
                    "value": round(snap.cpu.watts, 1),
                    "threshold_pct": self.cfg.cpu_watt_thresh_pct,
                })

        for payload in triggered:
            payload.update({
                "host": snap.cpu.label,
                "total_w": round(snap.total_watts, 1),
                "session_cost": round(self.session_cost(), 4),
            })
            asyncio.create_task(_post_webhook(url, payload))
