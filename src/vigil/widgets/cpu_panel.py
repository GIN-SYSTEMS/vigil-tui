"""CPUPanel widget — summary metrics + per-core utilisation bars.

V3.0 additions:
  - Throttle badge: compares avg core MHz to boost max
  - Efficiency score (perf/watt)
  - Baseline delta mode: shows +/- watts vs snapshotted idle
"""

from __future__ import annotations

from typing import Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from vigil import config
from vigil.collectors.system import CPUSnapshot
from vigil.session import (
    BaselineSnapshot,
    calc_cpu_efficiency,
    cpu_throttle_ratio,
    efficiency_label,
)


_CPU_COLOR  = "#00ffcc"
_CPU_DIM    = "#00aa88"
_WARN_COLOR = "#ffaa00"
_CRIT_COLOR = "#ff3300"
_OK_COLOR   = "#00cc88"


def _load_color(pct: float) -> str:
    if pct > 70:
        return _CRIT_COLOR
    if pct > 30:
        return _WARN_COLOR
    return _OK_COLOR


def _temp_color(temp_c: float) -> str:
    if temp_c > 85:
        return _CRIT_COLOR
    if temp_c > 70:
        return _WARN_COLOR
    return _CPU_COLOR


def _mhz_color(mhz: float, max_mhz: float) -> str:
    if max_mhz <= 0:
        return "#3a4a5a"
    ratio = mhz / max_mhz
    if ratio >= 0.95:
        return "#ffaa00"
    if ratio >= 0.75:
        return "#00cc88"
    return "#2a4a5a"


def _grid_columns(core_count: int) -> int:
    """Return the column count for the per-core grid based on logical cores.

    Picks the largest threshold from `config.CPU_GRID_THRESHOLDS` whose key is
    <= `core_count`. Defaults to 1 column when no threshold matches (e.g. 0
    cores reported), so the renderer never divides by zero.
    """
    cols = 1
    for threshold, col_count in config.CPU_GRID_THRESHOLDS:
        if core_count >= threshold:
            cols = col_count
    return max(1, cols)


class CPUPanel(Widget):
    """Left-column widget: CPU power summary and per-core utilisation grid."""

    BORDER_TITLE = "CPU METRICS"

    DEFAULT_CSS = """
    CPUPanel {
        border: double #004433;
        border-title-color: #00aa77;
        border-title-style: bold;
        height: 1fr;
        min-width: 30;
        background: #080c10;
        padding: 0 1;
        overflow-y: auto;
    }
    CPUPanel > Static {
        background: #080c10;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("", id="cpu_summary")
        yield Static("", id="cpu_cores")

    def update_data(
        self,
        snap: CPUSnapshot,
        cpu_tdp: float = 65.0,
        baseline: Optional[BaselineSnapshot] = None,
    ) -> None:
        self._render_summary(snap, cpu_tdp, baseline)
        self._render_cores(snap)

    # ── Private renderers ──────────────────────────────────────────────────

    def _render_summary(
        self,
        snap: CPUSnapshot,
        cpu_tdp: float,
        baseline: Optional[BaselineSnapshot],
    ) -> None:
        t = Text()

        # Power line
        t.append(f"{'Package':<9} ", style="#1e3028")
        t.append(f"{snap.watts:6.1f}W", style=f"bold {_CPU_COLOR}")
        t.append(f"  [{snap.source}]", style="#0e2018")

        if baseline is not None:
            delta = snap.watts - baseline.cpu_watts
            sign = "+" if delta >= 0 else ""
            col = _CRIT_COLOR if delta > 10 else _WARN_COLOR if delta > 0 else _OK_COLOR
            t.append(f"  {sign}{delta:.1f}W", style=col)
        t.append("\n")

        # Temperature
        t.append(f"{'Temp':<9} ", style="#1e3028")
        if snap.temp_c > 0:
            t.append(f"{snap.temp_c:.0f}°C", style=f"bold {_temp_color(snap.temp_c)}")
            if baseline is not None and baseline.cpu_temp > 0:
                dt = snap.temp_c - baseline.cpu_temp
                sign = "+" if dt >= 0 else ""
                col = _CRIT_COLOR if dt > 10 else _WARN_COLOR if dt > 3 else _OK_COLOR
                t.append(f"  {sign}{dt:.1f}°", style=col)
        else:
            t.append("N/A", style="#162020")
        t.append("\n")

        # Total utilisation
        bar_w = 20
        filled = int(snap.total_pct / 100 * bar_w)
        load_col = _load_color(snap.total_pct)
        t.append(f"{'Total':<9} ", style="#1e3028")
        t.append(f"{snap.total_pct:5.1f}%", style="#6a8a7a")
        t.append("  ")
        t.append("█" * filled, style=load_col)
        t.append("░" * (bar_w - filled), style="#0e1a18")
        t.append("\n")

        # Efficiency + throttle badge
        eff = calc_cpu_efficiency(snap, cpu_tdp)
        label, eff_col = efficiency_label(eff)
        t.append(f"{'Effic':<9} ", style="#1e3028")
        t.append(f"{eff:.2f}  ", style="#3a5a4a")
        t.append(f"[{label}]", style=f"bold {eff_col}")

        if snap.max_mhz > 0 and snap.core_mhz:
            ratio = cpu_throttle_ratio(snap)
            if ratio < 0.80:
                t.append("  ⚠ THROTTLE", style=f"bold {_CRIT_COLOR}")
        t.append("\n")

        self.query_one("#cpu_summary", Static).update(t)

    def _render_cores(self, snap: CPUSnapshot) -> None:
        t = Text()
        t.append("─ PER CORE ", style="#143020")
        t.append("─" * 17 + "\n", style="#0a1810")

        cores = snap.core_utils[: config.MAX_DISPLAY_CORES]
        mhz_list = snap.core_mhz
        max_mhz = snap.max_mhz

        if not cores:
            t.append("  no per-core data\n", style="#143020")
            self.query_one("#cpu_cores", Static).update(t)
            return

        cols = _grid_columns(len(cores))
        rows = (len(cores) + cols - 1) // cols
        col_sep = "  "
        bar_w = 8

        # Render row-major: row i contains cores [i, i+rows, i+2*rows, ...].
        # This keeps adjacent core indices in the same column for easier
        # eyeballing of NUMA blocks on high-core systems.
        for row in range(rows):
            for col in range(cols):
                idx = col * rows + row
                if idx >= len(cores):
                    continue
                if col > 0:
                    t.append(col_sep, style="#0a1810")

                util = cores[idx]
                filled = int(util / 100 * bar_w)
                color = _load_color(util)

                t.append(f"C{idx:<2}  ", style="#143020")
                t.append("█" * filled, style=color)
                t.append("░" * (bar_w - filled), style="#0e1a14")
                t.append(f" {util:3.0f}%", style=color)

                if idx < len(mhz_list) and mhz_list[idx] > 0:
                    ghz = mhz_list[idx] / 1000.0
                    mhz_col = _mhz_color(mhz_list[idx], max_mhz)
                    t.append(f"  {ghz:.1f}G", style=mhz_col)

            t.append("\n")

        self.query_one("#cpu_cores", Static).update(t)
