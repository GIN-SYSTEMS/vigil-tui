"""Abstract base for all hardware sensor collectors.

Every collector domain (CPU, GPU, RAM) derives from ``Collector`` and
implements a single ``read()`` method.  Call ``safe_read()`` from outside
the collector hierarchy — it absorbs all exceptions and returns a sentinel
``SensorReading`` so the TUI never crashes due to a missing driver or
insufficient privilege.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

log = logging.getLogger(__name__)

# All valid data-origin tags shown in the UI status bar.
Source = Literal["hwmon", "rapl", "nvml", "wmi", "estimate", "unavailable", "error"]


@dataclass(slots=True)
class SensorReading:
    """A single instantaneous measurement from one collector domain."""

    value: float        # power draw in watts
    source: Source      # where the data came from (shown in status bar)
    label: str          # human-readable channel name
    # Optional auxiliary fields: temperature, utilisation %, etc.
    extra: dict[str, float | str | int] = field(default_factory=dict)


class Collector(ABC):
    """Abstract base.  Subclasses implement ``read()``; callers use ``safe_read()``."""

    @abstractmethod
    def read(self) -> SensorReading:
        """Return a fresh reading.  May raise any exception on failure."""
        ...

    def safe_read(self) -> SensorReading:
        """Return a reading, converting all exceptions to graceful sentinels."""
        try:
            return self.read()
        except PermissionError as exc:
            log.debug("Permission denied in %s: %s", self.__class__.__name__, exc)
            return SensorReading(0.0, "unavailable", self.__class__.__name__)
        except Exception as exc:
            log.debug("Read error in %s: %s", self.__class__.__name__, exc)
            return SensorReading(0.0, "error", self.__class__.__name__)
