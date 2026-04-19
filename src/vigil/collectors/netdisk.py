"""Network and disk I/O rate collector.

Computes per-tick byte rates (bytes/s) by diffing consecutive psutil counters.
First call always returns zero rates (no previous sample to diff against).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import psutil


@dataclass(slots=True)
class NetSnapshot:
    bytes_sent_ps: float   # bytes/s upload
    bytes_recv_ps: float   # bytes/s download


@dataclass(slots=True)
class DiskSnapshot:
    read_bytes_ps: float   # bytes/s read
    write_bytes_ps: float  # bytes/s write


class NetDiskCollector:
    """Tracks delta-based I/O rates."""

    def __init__(self) -> None:
        self._last_time: Optional[float] = None
        self._last_net: Optional[object] = None
        self._last_disk: Optional[object] = None

    def collect(self) -> tuple[NetSnapshot, DiskSnapshot]:
        now = time.monotonic()

        try:
            net_now = psutil.net_io_counters()
        except Exception:
            net_now = None

        try:
            disk_now = psutil.disk_io_counters()
        except Exception:
            disk_now = None

        zero_net = NetSnapshot(0.0, 0.0)
        zero_disk = DiskSnapshot(0.0, 0.0)

        if self._last_time is None or self._last_net is None:
            self._last_time = now
            self._last_net = net_now
            self._last_disk = disk_now
            return zero_net, zero_disk

        dt = max(now - self._last_time, 0.001)

        # Network rates
        net = zero_net
        if net_now is not None and self._last_net is not None:
            try:
                sent = (net_now.bytes_sent - self._last_net.bytes_sent) / dt
                recv = (net_now.bytes_recv - self._last_net.bytes_recv) / dt
                net = NetSnapshot(max(0.0, sent), max(0.0, recv))
            except Exception:
                pass

        # Disk rates
        disk = zero_disk
        if disk_now is not None and self._last_disk is not None:
            try:
                read  = (disk_now.read_bytes  - self._last_disk.read_bytes)  / dt
                write = (disk_now.write_bytes - self._last_disk.write_bytes) / dt
                disk = DiskSnapshot(max(0.0, read), max(0.0, write))
            except Exception:
                pass

        self._last_time = now
        self._last_net = net_now
        self._last_disk = disk_now

        return net, disk
