"""TOML configuration loader.

Reads ~/.config/vigil/config.toml, creates it with defaults if absent.
All values are available as a frozen AppConfig dataclass.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

_CONFIG_DIR = Path.home() / ".config" / "vigil"
_CONFIG_PATH = _CONFIG_DIR / "config.toml"

_DEFAULT_TOML = """\
[power]
cpu_tdp_watts   = 65.0
gpu_tdp_watts   = 165.0

[sampling]
update_interval = 1.0
history_len     = 120

[cost]
# Electricity price per kWh in your local currency.
kwh_price = 4.5

[alerts]
# Set to "" to disable webhook alerts.
webhook_url      = ""
cpu_temp_thresh  = 90.0
cpu_watt_thresh_pct = 95.0

[display]
theme = "tactical"
"""


@dataclass(frozen=True)
class AppConfig:
    cpu_tdp_watts: float = 65.0
    gpu_tdp_watts: float = 165.0
    update_interval: float = 1.0
    history_len: int = 120
    kwh_price: float = 4.5
    webhook_url: str = ""
    cpu_temp_thresh: float = 90.0
    cpu_watt_thresh_pct: float = 95.0
    theme: str = "tactical"


def load_config() -> AppConfig:
    """Load config from disk, writing defaults if the file does not exist."""
    if not _CONFIG_PATH.exists():
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _CONFIG_PATH.write_text(_DEFAULT_TOML, encoding="utf-8")

    try:
        raw = tomllib.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        raw = {}

    power   = raw.get("power", {})
    samp    = raw.get("sampling", {})
    cost    = raw.get("cost", {})
    alerts  = raw.get("alerts", {})
    display = raw.get("display", {})

    return AppConfig(
        cpu_tdp_watts=float(power.get("cpu_tdp_watts", 65.0)),
        gpu_tdp_watts=float(power.get("gpu_tdp_watts", 165.0)),
        update_interval=float(samp.get("update_interval", 1.0)),
        history_len=int(samp.get("history_len", 120)),
        kwh_price=float(cost.get("kwh_price", 4.5)),
        webhook_url=str(alerts.get("webhook_url", "")),
        cpu_temp_thresh=float(alerts.get("cpu_temp_thresh", 90.0)),
        cpu_watt_thresh_pct=float(alerts.get("cpu_watt_thresh_pct", 95.0)),
        theme=str(display.get("theme", "tactical")),
    )
