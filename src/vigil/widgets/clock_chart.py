"""ClockChartPanel — center-column split companion to CombinedChartPanel.

Plots CPU average core frequency and GPU core frequency over time so the
user can see clock behaviour alongside the power chart.  Reuses
BrailleChart for rendering and shares the same history depth as the
power chart for visual alignment.

The Y-axis ceiling is derived once from the first non-zero ``max_mhz``
values reported by the collectors, so the chart auto-scales to whatever
hardware is in the box (laptop 4.5 GHz vs. desktop 5.7 GHz).
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label

from vigil import config
from vigil.widgets.braille_chart import BrailleChart


_DEFAULT_Y_MAX_MHZ: float = 5000.0


class ClockChartPanel(Widget):
    """Stacked beneath POWER HISTORY: CPU avg MHz + GPU core MHz over time."""

    BORDER_TITLE = "CLOCK HISTORY"

    DEFAULT_CSS = """
    ClockChartPanel {
        border: double #1a3040;
        border-title-color: #2a5060;
        border-title-style: bold;
        height: 1fr;
        min-height: 8;
        background: #090d12;
    }
    ClockChartPanel > Label {
        height: 1;
        background: #060810;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._y_max: float = _DEFAULT_Y_MAX_MHZ
        self._auto_scaled: bool = False

    def compose(self) -> ComposeResult:
        yield Label("", id="clock_legend")
        yield BrailleChart(
            y_max=self._y_max,
            history_len=config.HISTORY_LEN,
            series_colors=["#44ccff", "#ff8844"],
            id="clock_braille",
        )

    def push(
        self,
        cpu_avg_mhz: float,
        cpu_max_mhz: float,
        gpu_mhz: float,
        gpu_max_mhz: float,
    ) -> None:
        chart = self.query_one("#clock_braille", BrailleChart)

        # Auto-scale the Y-axis once we see the actual hardware ceilings.
        if not self._auto_scaled:
            ceiling = max(cpu_max_mhz, gpu_mhz, gpu_max_mhz, _DEFAULT_Y_MAX_MHZ * 0.5)
            if ceiling > 0:
                self._y_max = max(_DEFAULT_Y_MAX_MHZ, ceiling * 1.1)
                chart.set_y_max(self._y_max)
                self._auto_scaled = True

        chart.push(0, cpu_avg_mhz)
        chart.push(1, gpu_mhz)
        self._update_legend(cpu_avg_mhz, cpu_max_mhz, gpu_mhz, gpu_max_mhz)

    def reset(self) -> None:
        self.query_one("#clock_braille", BrailleChart).reset()

    def _update_legend(
        self,
        cpu_avg_mhz: float,
        cpu_max_mhz: float,
        gpu_mhz: float,
        gpu_max_mhz: float,
    ) -> None:
        t = Text(no_wrap=True, overflow="ellipsis")

        t.append("  ", style="")
        t.append("■ ", style="#44ccff")
        t.append("CPU avg ", style="#2a3a4a")
        if cpu_avg_mhz > 0:
            t.append(f"{cpu_avg_mhz / 1000.0:4.2f}GHz", style="bold #44ccff")
            if cpu_max_mhz > 0:
                t.append(f" / {cpu_max_mhz / 1000.0:.1f}", style="#1a2838")
        else:
            t.append("N/A", style="#1a2838")

        t.append("   ", style="")
        t.append("■ ", style="#ff8844")
        t.append("GPU core ", style="#2a3a4a")
        if gpu_mhz > 0:
            t.append(f"{gpu_mhz:4.0f}MHz", style="bold #ff8844")
            if gpu_max_mhz > 0:
                t.append(f" / {gpu_max_mhz}", style="#1a2838")
        else:
            t.append("N/A", style="#1a2838")

        t.append(f"   ↕ {self._y_max / 1000.0:.1f}GHz", style="#1a2838")

        self.query_one("#clock_legend", Label).update(t)
