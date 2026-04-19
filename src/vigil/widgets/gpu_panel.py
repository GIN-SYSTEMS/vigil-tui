"""GPUPanel widget — full NVIDIA metrics display.

V3.0 additions:
  - Throttle badge: compares core_mhz to max_core_mhz
  - Efficiency score (perf/watt)
  - Baseline delta mode
"""

from __future__ import annotations

from typing import Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from vigil.collectors.system import GPUSnapshot
from vigil.session import (
    BaselineSnapshot,
    calc_gpu_efficiency,
    efficiency_label,
    gpu_throttle_ratio,
)


_GPU_COLOR   = "#ffaa00"
_GPU_DIM     = "#cc8800"
_VRAM_COLOR  = "#aa77ff"
_FAN_COLOR   = "#44ccff"
_CRIT_COLOR  = "#ff3300"
_OK_COLOR    = "#00cc88"


def _bar_color(pct: float) -> str:
    if pct > 85:
        return _CRIT_COLOR
    if pct > 60:
        return _GPU_COLOR
    return _OK_COLOR


def _temp_color(temp_c: float) -> str:
    if temp_c > 85:
        return _CRIT_COLOR
    if temp_c > 70:
        return _GPU_COLOR
    return "#ffcc44"


def _bar(pct: float, width: int, color: str) -> Text:
    filled = int(min(pct, 100) / 100 * width)
    t = Text()
    t.append("█" * filled, style=color)
    t.append("░" * (width - filled), style="#0e1520")
    return t


class GPUPanel(Widget):
    """Right-column widget: full NVIDIA GPU metrics."""

    DEFAULT_CSS = """
    GPUPanel {
        border: double #443300;
        border-title-color: #aa7700;
        border-title-style: bold;
        height: auto;
        min-width: 32;
        background: #0a0d10;
        padding: 0 1;
    }
    GPUPanel > Static {
        background: #0a0d10;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Initialising GPU…", id="gpu_content")

    def update_data(
        self,
        snap: GPUSnapshot,
        gpu_tdp: float = 165.0,
        baseline: Optional[BaselineSnapshot] = None,
    ) -> None:
        self.border_title = snap.name[:28] or "GPU METRICS"
        self.query_one("#gpu_content", Static).update(
            self._build(snap, gpu_tdp, baseline)
        )

    # ── Renderer ───────────────────────────────────────────────────────────

    def _build(
        self,
        snap: GPUSnapshot,
        gpu_tdp: float,
        baseline: Optional[BaselineSnapshot],
    ) -> Text:
        t = Text()
        bar_w = 18

        # ── Power + temp ──────────────────────────────────────────────────
        t.append(f"{'Power':<8} ", style="#2a2010")
        t.append(f"{snap.watts:6.1f}W", style=f"bold {_GPU_COLOR}")
        t.append(f"  [{snap.source}]", style="#1a1408")
        if baseline is not None:
            delta = snap.watts - baseline.gpu_watts
            sign = "+" if delta >= 0 else ""
            col = _CRIT_COLOR if delta > 10 else _GPU_COLOR if delta > 0 else _OK_COLOR
            t.append(f"  {sign}{delta:.1f}W", style=col)
        t.append("\n")

        t.append(f"{'Temp':<8} ", style="#2a2010")
        if snap.temp_c > 0:
            t.append(f"{snap.temp_c:.0f}°C", style=f"bold {_temp_color(snap.temp_c)}")
        else:
            t.append("N/A", style="#181208")
        t.append("\n")

        # Efficiency + throttle
        eff = calc_gpu_efficiency(snap, gpu_tdp)
        label, eff_col = efficiency_label(eff)
        t.append(f"{'Effic':<8} ", style="#2a2010")
        t.append(f"{eff:.2f}  ", style="#4a3a1a")
        t.append(f"[{label}]", style=f"bold {eff_col}")

        if snap.max_core_mhz > 0 and snap.core_mhz > 0:
            ratio = gpu_throttle_ratio(snap)
            if ratio < 0.80:
                t.append(f"  ⚠ THROTTLE", style=f"bold {_CRIT_COLOR}")
        t.append("\n")

        # ── Performance section ───────────────────────────────────────────
        t.append("\n─ PERFORMANCE ", style="#1e1808")
        t.append("─" * 14 + "\n", style="#120e04")

        util_color = _bar_color(snap.util_pct)
        t.append(f"{'Util':<8} ", style="#2a2010")
        t.append_text(_bar(snap.util_pct, bar_w, util_color))
        t.append(f"  {snap.util_pct:3d}%\n", style=util_color)

        t.append(f"{'Core':<8} ", style="#2a2010")
        if snap.core_mhz:
            boost_info = f" / {snap.max_core_mhz}" if snap.max_core_mhz else ""
            t.append(f"{snap.core_mhz:5d}{boost_info} MHz\n", style="#7a6030")
        else:
            t.append("N/A\n", style="#181208")

        t.append(f"{'Mem':<8} ", style="#2a2010")
        if snap.mem_mhz:
            t.append(f"{snap.mem_mhz:5d} MHz\n", style="#5a4820")
        else:
            t.append("N/A\n", style="#181208")

        # ── VRAM section ──────────────────────────────────────────────────
        t.append("\n─ VRAM ", style="#1e1808")
        t.append("─" * 21 + "\n", style="#120e04")

        if snap.vram_total_mb > 0:
            used_gb = snap.vram_used_mb / 1024.0
            total_gb = snap.vram_total_mb / 1024.0
            vram_pct = snap.vram_used_mb / snap.vram_total_mb * 100.0

            t.append(f"  {used_gb:.1f}", style="#7a66aa")
            t.append(f" / {total_gb:.1f} GB", style="#3a2a60")
            t.append(f"  ({vram_pct:.0f}%)\n", style="#2a1a44")
            t.append("  ")
            t.append_text(_bar(vram_pct, bar_w + 6, _VRAM_COLOR))
            t.append("\n")
        else:
            t.append("  N/A\n", style="#181208")

        # ── Cooling section ───────────────────────────────────────────────
        if snap.fan_pct > 0:
            t.append("\n─ COOLING ", style="#1e1808")
            t.append("─" * 18 + "\n", style="#120e04")
            t.append(f"{'Fan':<8} ", style="#2a2010")
            t.append_text(_bar(snap.fan_pct, bar_w, _FAN_COLOR))
            t.append(f"  {snap.fan_pct:3d}%\n", style=_FAN_COLOR)

        return t
