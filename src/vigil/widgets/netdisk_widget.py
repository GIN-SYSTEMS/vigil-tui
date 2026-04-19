"""NetDiskWidget — compact network + disk I/O rates display."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from vigil.collectors.netdisk import DiskSnapshot, NetSnapshot


def _human(bps: float) -> str:
    """Format bytes/s as human-readable string with SI prefix."""
    if bps >= 1_073_741_824:
        return f"{bps/1_073_741_824:5.1f} GB/s"
    if bps >= 1_048_576:
        return f"{bps/1_048_576:5.1f} MB/s"
    if bps >= 1_024:
        return f"{bps/1_024:5.1f} KB/s"
    return f"{bps:5.0f}  B/s"


class NetDiskWidget(Static):
    """Single-line footer showing live net ↑↓ and disk R/W rates."""

    DEFAULT_CSS = """
    NetDiskWidget {
        height: 2;
        border-top: solid #0d1a28;
        background: #060810;
        padding: 0 1;
        content-align: left middle;
    }
    """

    def set_readings(self, net: NetSnapshot, disk: DiskSnapshot) -> None:
        t = Text(no_wrap=True)

        t.append("  NET  ", style="#0e1a28")
        t.append("↑ ", style="#006688")
        t.append(_human(net.bytes_sent_ps), style="#44aaff")
        t.append("  ↓ ", style="#882200")
        t.append(_human(net.bytes_recv_ps), style="#ff6644")

        t.append("     DISK  ", style="#0e1a28")
        t.append("R ", style="#225588")
        t.append(_human(disk.read_bytes_ps), style="#5588cc")
        t.append("  W ", style="#664400")
        t.append(_human(disk.write_bytes_ps), style="#ff9944")

        self.update(t)
