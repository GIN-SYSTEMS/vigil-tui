"""NVIDIA GPU collector via NVML (pynvml).

Reads a full suite of GPU metrics in a single pass per tick:
  - Power draw (W)
  - Die temperature (°C)
  - GPU + memory utilisation (%)
  - VRAM used / total (MB)
  - Fan speed (% of max — NVML does not expose RPM on most consumer cards)
  - Graphics core clock (MHz)
  - Memory bus clock (MHz)

All reads are wrapped individually; a failing sensor does not abort the
full read — it leaves the field at its zero default.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from vigil.collectors.base import Collector, SensorReading

log = logging.getLogger(__name__)


class GPUCollector(Collector):
    """Reads NVIDIA GPU metrics via NVML."""

    def __init__(self, device_index: int = 0) -> None:
        self._index = device_index
        self._handle: Optional[object] = None
        self._name: str = "GPU"
        self._nvml_ok: bool = False
        self._init()

    def _init(self) -> None:
        try:
            import pynvml  # type: ignore[import]

            pynvml.nvmlInit()
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(self._index)
            raw = pynvml.nvmlDeviceGetName(self._handle)
            self._name = raw.decode() if isinstance(raw, bytes) else str(raw)
            self._nvml_ok = True
            log.info("NVML initialised: %s (device %d)", self._name, self._index)
        except Exception as exc:
            log.debug("NVML unavailable: %s", exc)

    # ── Collector interface ────────────────────────────────────────────────

    def read(self) -> SensorReading:
        if not self._nvml_ok or self._handle is None:
            return SensorReading(0.0, "unavailable", "GPU (no NVML)")

        import pynvml  # type: ignore[import]

        # Power (milliwatts → watts)
        mw = pynvml.nvmlDeviceGetPowerUsage(self._handle)
        watts = mw / 1_000.0

        extra: dict[str, Any] = {}

        # Temperature
        try:
            extra["temp_c"] = pynvml.nvmlDeviceGetTemperature(
                self._handle, pynvml.NVML_TEMPERATURE_GPU
            )
        except Exception:
            extra["temp_c"] = 0

        # Utilisation rates
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(self._handle)
            extra["gpu_util"] = util.gpu
            extra["mem_util"] = util.memory
        except Exception:
            extra["gpu_util"] = 0
            extra["mem_util"] = 0

        # VRAM
        try:
            mem = pynvml.nvmlDeviceGetMemoryInfo(self._handle)
            extra["vram_used_mb"] = mem.used // (1024 * 1024)
            extra["vram_total_mb"] = mem.total // (1024 * 1024)
        except Exception:
            extra["vram_used_mb"] = 0
            extra["vram_total_mb"] = 0

        # Fan speed (% of max; NVML lacks RPM on most consumer GPUs)
        try:
            extra["fan_pct"] = pynvml.nvmlDeviceGetFanSpeed(self._handle)
        except Exception:
            extra["fan_pct"] = 0

        # Clocks (current + boost max)
        try:
            extra["core_mhz"] = pynvml.nvmlDeviceGetClockInfo(
                self._handle, pynvml.NVML_CLOCK_GRAPHICS
            )
            extra["mem_mhz"] = pynvml.nvmlDeviceGetClockInfo(
                self._handle, pynvml.NVML_CLOCK_MEM
            )
        except Exception:
            extra["core_mhz"] = 0
            extra["mem_mhz"] = 0

        try:
            extra["max_core_mhz"] = pynvml.nvmlDeviceGetMaxClockInfo(
                self._handle, pynvml.NVML_CLOCK_GRAPHICS
            )
        except Exception:
            extra["max_core_mhz"] = 0

        return SensorReading(watts, "nvml", self._name, extra)

    # ── Accessors ──────────────────────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        return self._nvml_ok

    @property
    def device_name(self) -> str:
        return self._name
