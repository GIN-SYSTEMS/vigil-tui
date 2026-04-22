"""TerminalInfoApp v3.0 — Ultimate Edition TUI Power Monitor.

Layout (120+ columns required):

  ┌─ PowerHeader (h=3) ─────────────────────────────────────────────────────┐
  │  ▐ TERMINALINFO ▌  ████████████████░░░░  187.3 W / 260 W  [cpu:hwmon]  │
  ├─ #left-col (w=32) ─┬─ #center-col (1fr) ──────┬─ #right-col (w=36) ───┤
  │ CPU METRICS        │ POWER HISTORY             │ RTX 4070 Ti            │
  │ + efficiency badge │ + legend                  │ + efficiency badge     │
  │ + throttle badge   │                           │ + throttle badge       │
  │ + baseline delta   │ PROCESSES                 │ RAM bar                │
  │ + per-core bars    │ + sparklines              │ Net/Disk I/O           │
  ├────────────────────┴──────────────────────────┴───────────────────────┤
  │ FINANCIAL  /hr ₺0.82   /day ₺19.6   session 0.12h ₺0.0014             │
  ├────────────────────────────────────────────────────────────────────────┤
  │  OS  │  arch  │  host  │  up 0h 04m  │  cpu:hwmon  │  ⚠ THROTTLE     │
  └────────────────────────────────────────────────────────────────────────┘

Key bindings:
  q / Ctrl+C   Quit
  p            Pause / resume sampling
  r            Reset chart ring-buffers
  +            Zoom Y-axis in  (lower ceiling = more detail)
  -            Zoom Y-axis out (raise ceiling to see large spikes)
  b            Snapshot baseline (press again to clear)
  s            Save SVG screenshot to current directory
  t            Toggle theme: TacticalCyberpunk ↔ GhostWhite
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Label, Static

from vigil import config
from vigil.collectors.system import SystemCollector, SystemSnapshot
from vigil.config_manager import AppConfig, load_config
from vigil.session import (
    SessionState,
    cpu_throttle_ratio,
    gpu_throttle_ratio,
)
from vigil.widgets.braille_chart import BrailleChart
from vigil.widgets.clock_chart import ClockChartPanel
from vigil.widgets.cpu_panel import CPUPanel
from vigil.widgets.financial_widget import FinancialWidget
from vigil.widgets.gpu_panel import GPUPanel
from vigil.widgets.help_overlay import HelpOverlay
from vigil.widgets.netdisk_widget import NetDiskWidget
from vigil.widgets.power_header import PowerHeader
from vigil.widgets.process_table import ProcessTable
from vigil.widgets.status_bar import StatusBar

def _get_css_path() -> Path:
    """Resolve CSS path for both normal and PyInstaller-frozen execution."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "TacticalCyberpunk.tcss"
    return Path(__file__).parent / "TacticalCyberpunk.tcss"


_CSS_PATH = _get_css_path()


# ── Combined power history panel ───────────────────────────────────────────

class CombinedChartPanel(Widget):
    """Center-column hero widget: CPU+GPU power history + session stats."""

    BORDER_TITLE = "POWER HISTORY"

    DEFAULT_CSS = """
    CombinedChartPanel {
        border: double #0e2030;
        border-title-color: #1a4050;
        border-title-style: bold;
        height: 1fr;
        min-height: 10;
        background: #060a0e;
    }
    CombinedChartPanel > Label {
        height: 1;
        background: #050810;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._peak_total: float = 0.0
        self._sample_count: int = 0
        self._sum_total: float = 0.0

    def compose(self) -> ComposeResult:
        yield Label("", id="chart_legend")
        yield Label("", id="chart_stats")
        yield BrailleChart(
            y_max=config.CHART_COMBINED_Y_MAX,
            history_len=config.HISTORY_LEN,
            series_colors=["#00ffcc", "#ffaa00"],
            id="combined_braille",
        )

    def push(
        self,
        cpu_watts: float,
        cpu_src: str,
        gpu_watts: float,
        gpu_src: str,
    ) -> None:
        chart = self.query_one("#combined_braille", BrailleChart)
        chart.push(0, cpu_watts)
        chart.push(1, gpu_watts)

        total = cpu_watts + gpu_watts
        self._peak_total = max(self._peak_total, total)
        self._sum_total += total
        self._sample_count += 1

        self._update_legend(cpu_watts, cpu_src, gpu_watts, gpu_src, chart.y_max)
        self._update_stats(total)

    def chart(self) -> BrailleChart:
        return self.query_one("#combined_braille", BrailleChart)

    def reset(self) -> None:
        self._peak_total = 0.0
        self._sample_count = 0
        self._sum_total = 0.0

    def _update_legend(
        self,
        cpu_w: float,
        cpu_src: str,
        gpu_w: float,
        gpu_src: str,
        y_max: float,
    ) -> None:
        t = Text(no_wrap=True, overflow="ellipsis")

        t.append("  ")
        t.append("■ ", style="#00ffcc")
        t.append("CPU ", style="#1a3028")
        t.append(f"{cpu_w:5.1f}W", style="bold #00ffcc")
        t.append(f" [{cpu_src}]", style="#0e1e18")

        t.append("   ")
        t.append("■ ", style="#ffaa00")
        t.append("GPU ", style="#2a2010")
        t.append(f"{gpu_w:5.1f}W", style="bold #ffaa00")
        t.append(f" [{gpu_src}]", style="#1a1408")

        t.append(f"   ↕ {y_max:.0f}W", style="#0e1a28")

        self.query_one("#chart_legend", Label).update(t)

    def _update_stats(self, current_total: float) -> None:
        avg = self._sum_total / max(self._sample_count, 1)
        t = Text(no_wrap=True, overflow="ellipsis")

        t.append("  now ", style="#0e1a28")
        t.append(f"{current_total:5.1f}W", style="#c0d0e0")

        t.append("   peak ", style="#0e1a28")
        t.append(f"{self._peak_total:5.1f}W", style="#ff6644")

        t.append("   avg ", style="#0e1a28")
        t.append(f"{avg:5.1f}W", style="#44aaff")

        t.append(f"   samples {self._sample_count}", style="#0a1420")

        self.query_one("#chart_stats", Label).update(t)


# ── RAM bar (bottom of right column) ──────────────────────────────────────

class RAMBar(Static):
    """Compact RAM utilisation widget displayed below GPUPanel."""

    DEFAULT_CSS = """
    RAMBar {
        height: 2;
        border-top: solid #0d1a28;
        background: #060810;
        padding: 0 1;
        content-align: left middle;
    }
    """

    def set_reading(
        self, used_gb: float, total_gb: float, pct: float, watts: float
    ) -> None:
        bar_w = 14
        filled = int(min(pct, 100) / 100 * bar_w)

        t = Text(no_wrap=True)
        t.append("  RAM  ", style="#2a3a4a")
        t.append("█" * filled, style="#006644")
        t.append("░" * (bar_w - filled), style="#1a2838")
        t.append(f"  {used_gb:.1f}", style="#00ccaa")
        t.append(f" / {total_gb:.0f} GB", style="#2a3a4a")
        t.append(f"   {watts:.1f}W", style="#2a5040")
        self.update(t)


# ── Root application ───────────────────────────────────────────────────────

class TerminalInfoApp(App[None]):
    """vigil v1.0 — Ultimate Edition TUI power monitor."""

    CSS_PATH = _CSS_PATH
    TITLE = "vigil v1"
    SUB_TITLE = "ultimate power monitor"

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("asterisk", "help", "Help"),
        Binding("p", "toggle_pause", "Pause"),
        Binding("r", "reset_charts", "Reset"),
        Binding("+", "zoom_in", "Zoom +"),
        Binding("-", "zoom_out", "Zoom −"),
        Binding("b", "toggle_baseline", "Baseline"),
        Binding("s", "screenshot", "Screenshot"),
        Binding("t", "toggle_theme", "Theme"),
    ]

    def __init__(
        self,
        log_enabled: bool = False,
        process_filter: str | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._log_enabled = log_enabled
        self._process_filter = process_filter
        self._app_cfg: AppConfig = load_config()

    # ── Layout ─────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield PowerHeader(id="header")

        with Horizontal(id="main"):
            with Vertical(id="left-col"):
                yield CPUPanel(id="cpu_panel")

            with Vertical(id="center-col"):
                yield CombinedChartPanel(id="chart_panel")
                yield ClockChartPanel(id="clock_panel")
                yield ProcessTable(id="proc_table")

            with Vertical(id="right-col"):
                yield GPUPanel(id="gpu_panel")
                yield RAMBar(id="ram_bar")
                yield NetDiskWidget(id="netdisk_bar")

        yield FinancialWidget(currency=self._app_cfg.currency, id="financial_bar")
        yield StatusBar(id="status")

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self._collector = SystemCollector(process_filter=self._process_filter)
        self._paused = False
        self._y_max = config.CHART_COMBINED_Y_MAX
        self._ghost_white = self._app_cfg.theme == "ghost"

        cfg = self._app_cfg
        self._session = SessionState(
            cfg=cfg,
            log_enabled=self._log_enabled,
        )

        if self._ghost_white:
            self.screen.add_class("ghost-white")

        self.set_interval(cfg.update_interval, self._tick)

    # ── Tick handler ───────────────────────────────────────────────────────

    def _tick(self) -> None:
        if self._paused:
            return

        t0 = time.monotonic()
        snap: SystemSnapshot = self._collector.collect()
        elapsed_ms = (time.monotonic() - t0) * 1_000.0

        cfg = self._app_cfg
        baseline = self._session.baseline

        # Update session state (cost accumulation, optional logging)
        self._session.tick(snap, cfg.update_interval)

        # Fire-and-forget webhook alerts (non-blocking)
        import asyncio
        asyncio.create_task(self._session.check_and_alert(snap))

        # Throttle detection — only flag under real load (not idle clock-down)
        cpu_throttled = (
            snap.cpu.max_mhz > 0
            and bool(snap.cpu.core_mhz)
            and snap.cpu.total_pct > 10.0
            and cpu_throttle_ratio(snap.cpu) < 0.80
        )
        gpu_throttled = (
            snap.gpu.max_core_mhz > 0
            and snap.gpu.core_mhz > 0
            and snap.gpu.util_pct > 5
            and gpu_throttle_ratio(snap.gpu) < 0.80
        )

        # Header
        self.query_one("#header", PowerHeader).update_display(
            total_watts=snap.total_watts,
            cpu_source=snap.cpu.source,
            gpu_source=snap.gpu.source,
            paused=self._paused,
        )

        # CPU panel (left column)
        self.query_one("#cpu_panel", CPUPanel).update_data(
            snap.cpu,
            cpu_tdp=cfg.cpu_tdp_watts,
            baseline=baseline,
        )

        # Combined chart (center, top)
        self.query_one("#chart_panel", CombinedChartPanel).push(
            snap.cpu.watts, snap.cpu.source,
            snap.gpu.watts, snap.gpu.source,
        )

        # Clock chart (center, middle)
        cpu_avg_mhz = (
            sum(snap.cpu.core_mhz) / len(snap.cpu.core_mhz)
            if snap.cpu.core_mhz else 0.0
        )
        self.query_one("#clock_panel", ClockChartPanel).push(
            cpu_avg_mhz=cpu_avg_mhz,
            cpu_max_mhz=snap.cpu.max_mhz,
            gpu_mhz=float(snap.gpu.core_mhz),
            gpu_max_mhz=float(snap.gpu.max_core_mhz),
        )

        # Process table (center, bottom)
        self.query_one("#proc_table", ProcessTable).update(snap.processes)

        # GPU panel (right column, top)
        self.query_one("#gpu_panel", GPUPanel).update_data(
            snap.gpu,
            gpu_tdp=cfg.gpu_tdp_watts,
            baseline=baseline,
        )

        # RAM bar (right column)
        self.query_one("#ram_bar", RAMBar).set_reading(
            used_gb=snap.ram.used_gb,
            total_gb=snap.ram.total_gb,
            pct=snap.ram.percent,
            watts=snap.ram.watts,
        )

        # Net/disk bar (right column)
        self.query_one("#netdisk_bar", NetDiskWidget).set_readings(snap.net, snap.disk)

        # Financial bar (bottom of main area)
        baseline_delta: float | None = None
        if baseline is not None:
            baseline_delta = snap.total_watts - baseline.total_watts

        self.query_one("#financial_bar", FinancialWidget).set_costs(
            per_hour=self._session.cost_per_hour(snap.total_watts),
            per_day=self._session.cost_per_day(snap.total_watts),
            session=self._session.session_cost(),
            session_duration_s=self._session.session_duration_s(),
            baseline_delta_w=baseline_delta,
        )

        # Status bar
        self.query_one("#status", StatusBar).update_display(
            cpu_source=snap.cpu.source,
            gpu_source=snap.gpu.source,
            sample_ms=elapsed_ms,
            cpu_throttled=cpu_throttled,
            gpu_throttled=gpu_throttled,
            baseline_active=baseline is not None,
        )

    # ── Key actions ────────────────────────────────────────────────────────

    def action_help(self) -> None:
        self.push_screen(HelpOverlay())

    def action_toggle_pause(self) -> None:
        self._paused = not self._paused
        hdr = self.query_one("#header", PowerHeader)
        hdr.update_display(
            hdr._total_w, hdr._cpu_src, hdr._gpu_src, paused=self._paused
        )

    def action_reset_charts(self) -> None:
        for chart in self.query(BrailleChart):
            chart.reset()
        self.query_one("#chart_panel", CombinedChartPanel).reset()

    def action_zoom_in(self) -> None:
        self._y_max = max(10.0, self._y_max * 0.75)
        self.query_one("#combined_braille", BrailleChart).set_y_max(self._y_max)

    def action_zoom_out(self) -> None:
        self._y_max = min(600.0, self._y_max * 1.33)
        self.query_one("#combined_braille", BrailleChart).set_y_max(self._y_max)

    def action_toggle_baseline(self) -> None:
        if self._session.baseline is not None:
            self._session.clear_baseline()
        else:
            snap = self._collector.collect()
            self._session.set_baseline(snap)

    def action_screenshot(self) -> None:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        path = Path.cwd() / f"vigil_{timestamp}.svg"
        self.save_screenshot(str(path))

    def action_toggle_theme(self) -> None:
        self._ghost_white = not self._ghost_white
        if self._ghost_white:
            self.screen.add_class("ghost-white")
        else:
            self.screen.remove_class("ghost-white")
