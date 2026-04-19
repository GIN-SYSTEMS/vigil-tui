"""ProcessTable widget — top-N processes with mini load bars + sparklines.

Columns:
    PID     │ PROCESS             │ CPU load bar    │  CPU%  │  EST.W  │ SPARK

Sparkline: 10-char block-char trend of last 30 CPU% samples per PID.
Mini-bar colours (CPU%):
  green  (#006644)  < 30%  — light load
  amber  (#cc8800)  30–70% — moderate
  red    (#cc4400)  > 70%  — heavy
"""

from __future__ import annotations

from collections import deque

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable

from vigil.collectors.system import ProcessEntry

_SPARKS = " ▁▂▃▄▅▆▇█"
_SPARK_HISTORY = 10  # samples kept per PID


def _load_color(pct: float) -> str:
    if pct > 70:
        return "#cc4400"
    if pct > 30:
        return "#cc8800"
    return "#006644"


def _sparkline(values: deque[float]) -> str:
    if not values:
        return " " * _SPARK_HISTORY
    peak = max(values) or 1.0
    chars = []
    # Pad left if history is shorter than target width
    pad = _SPARK_HISTORY - len(values)
    chars.extend([" "] * pad)
    for v in values:
        idx = int(v / peak * (len(_SPARKS) - 1))
        chars.append(_SPARKS[idx])
    return "".join(chars)


class ProcessTable(Widget):
    """Horizontal process list ranked by estimated wattage."""

    BORDER_TITLE = "PROCESSES"

    DEFAULT_CSS = """
    ProcessTable {
        border: double #1a3040;
        border-title-color: #2a5060;
        border-title-style: bold;
        height: 12;
        background: #090d12;
    }
    ProcessTable > DataTable {
        background: #090d12;
        color: #4a6070;
        height: 1fr;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        # PID → deque of recent cpu_pct samples
        self._spark_history: dict[int, deque[float]] = {}

    def compose(self) -> ComposeResult:
        yield DataTable(show_cursor=False, zebra_stripes=True)

    def on_mount(self) -> None:
        t = self.query_one(DataTable)
        t.add_column("PID", width=7)
        t.add_column("PROCESS", width=18)
        t.add_column("LOAD", width=17)
        t.add_column("EST.W", width=6)
        t.add_column("TREND", width=_SPARK_HISTORY + 1)

    def update(self, processes: list[ProcessEntry]) -> None:  # type: ignore[override]
        t = self.query_one(DataTable)
        t.clear()

        # Prune history for PIDs that have exited
        live_pids = {p.pid for p in processes}
        stale = [pid for pid in self._spark_history if pid not in live_pids]
        for pid in stale:
            del self._spark_history[pid]

        for p in processes:
            # Update sparkline history
            if p.pid not in self._spark_history:
                self._spark_history[p.pid] = deque(maxlen=_SPARK_HISTORY)
            self._spark_history[p.pid].append(p.cpu_pct)

            color = _load_color(p.cpu_pct)
            bar_w = 10
            filled = int(min(p.cpu_pct, 100) / 100 * bar_w)
            bar_str = "█" * filled + "░" * (bar_w - filled)

            pid_cell = Text(str(p.pid), style="#1a2838", justify="right")
            name_cell = Text(p.name, style=color)

            load_cell = Text()
            load_cell.append(bar_str, style=color)
            load_cell.append(f" {p.cpu_pct:4.1f}%", style=color)

            w_cell = Text(f"{p.est_watts:.2f}", style="#2a5040", justify="right")

            spark_str = _sparkline(self._spark_history[p.pid])
            spark_cell = Text(spark_str, style="#1a3830")

            t.add_row(pid_cell, name_cell, load_cell, w_cell, spark_cell)
