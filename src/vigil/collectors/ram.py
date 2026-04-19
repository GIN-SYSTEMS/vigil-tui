"""RAM utilisation collector with DDR4 power estimation.

There is no standard OS interface for reading DRAM power draw without
specialised firmware.  This module estimates it via a DDR4 power model:

    P = slots × WATTS_PER_8GB × (0.5 + 0.5 × utilisation)

The 0.5 base accounts for quiescent DRAM refresh power; the variable
component scales linearly with utilisation.  Accuracy is ±30 % — sufficient
for dashboard situational awareness.
"""

from __future__ import annotations

import psutil

from vigil import config
from vigil.collectors.base import Collector, SensorReading


class RAMCollector(Collector):
    """Reports RAM utilisation and estimates DRAM power in watts."""

    def read(self) -> SensorReading:
        mem = psutil.virtual_memory()

        total_gb = mem.total / (1024 ** 3)
        used_gb = mem.used / (1024 ** 3)
        util_frac = mem.percent / 100.0

        # Round up to the nearest 8 GB slot boundary for the slot count.
        num_slots = max(1, -(-int(total_gb) // 8))   # ceiling division
        watts = num_slots * config.RAM_WATTS_PER_8GB * (0.5 + 0.5 * util_frac)

        return SensorReading(
            watts,
            "estimate",
            "RAM",
            {
                "used_gb": round(used_gb, 1),
                "total_gb": round(total_gb, 1),
                "percent": round(mem.percent, 1),
            },
        )
