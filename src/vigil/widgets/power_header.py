"""PowerHeader widget — top-of-screen title bar and total-TDP gauge.

Visual layout (3 terminal rows, full width):

    ▓░ VIGIL ░▓  ████████████░░░░  18.8 W / 260 W  [cpu:estimate  gpu:nvml]

Gauge zones:
  green  (0–65%)   — nominal load
  amber  (65–85%)  — elevated
  red    (> 85%)   — near-TDP ceiling
"""

from __future__ import annotations

from rich.text import Text
from textual.widget import Widget

from vigil import config


class PowerHeader(Widget):
    """Full-width header: wordmark + tri-zone TDP gauge + source provenance."""

    DEFAULT_CSS = """
    PowerHeader {
        height: 3;
        background: #030507;
        border-bottom: heavy #0a1828;
        padding: 0 2;
        content-align: left middle;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._total_w: float = 0.0
        self._cpu_src: str = "—"
        self._gpu_src: str = "—"
        self._paused: bool = False

    def update_display(
        self,
        total_watts: float,
        cpu_source: str,
        gpu_source: str,
        *,
        paused: bool = False,
    ) -> None:
        self._total_w = total_watts
        self._cpu_src = cpu_source
        self._gpu_src = gpu_source
        self._paused = paused
        self.refresh()

    def render(self) -> Text:
        t = Text(no_wrap=True, overflow="ellipsis")

        # Wordmark
        t.append("▓", style="#003322")
        t.append("░", style="#006644")
        t.append(" VIGIL ", style="bold #00ffcc")
        t.append("░", style="#006644")
        t.append("▓", style="#003322")
        t.append("  ", style="")

        # Tri-zone TDP gauge (28 cells)
        y_max = config.SYSTEM_TDP_WATTS
        pct = min(self._total_w / max(y_max, 1.0), 1.0)
        total_cells = 28
        filled = int(pct * total_cells)
        empty = total_cells - filled

        green_cap   = int(total_cells * 0.65)
        amber_cap   = int(total_cells * 0.85)
        green_cells = min(filled, green_cap)
        amber_cells = min(max(filled - green_cap, 0), amber_cap - green_cap)
        red_cells   = max(filled - green_cap - amber_cells, 0)

        t.append("█" * green_cells, style="#00cc88")
        t.append("█" * amber_cells, style="#ffaa00")
        t.append("█" * red_cells,   style="#ff3300")
        t.append("░" * empty,       style="#0d1e2a")

        # Wattage
        t.append(f"  {self._total_w:7.1f}", style="bold #e0eaf4")
        t.append(" W", style="#3a5060")
        t.append(f" / {y_max:.0f} W", style="#1a2c3a")

        # Source provenance
        t.append("  [", style="#091218")
        t.append(f"cpu:{self._cpu_src}", style="#00aa77")
        t.append("  ", style="#091218")
        t.append(f"gpu:{self._gpu_src}", style="#bb8800")
        t.append("]", style="#091218")

        # Pause indicator
        if self._paused:
            t.append("  ⏸ PAUSED", style="bold #ffaa00")

        return t
