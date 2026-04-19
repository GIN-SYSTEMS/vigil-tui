"""HelpOverlay — in-app keybinding reference modal.

Triggered by pressing ``?``.  Dismissed by pressing ``?``, ``q``,
``escape``, or clicking outside.  Designed to be lightweight: a single
``Static`` widget, no input handling beyond dismiss.
"""

from __future__ import annotations

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static

_BINDINGS: list[tuple[str, str, str]] = [
    # key, action, description
    ("q / Ctrl+C", "quit",          "Exit vigil"),
    ("p",          "pause",         "Pause / resume sampling"),
    ("r",          "reset",         "Clear chart ring-buffers"),
    ("+",          "zoom in",       "Lower Y-axis ceiling (more detail)"),
    ("−",          "zoom out",      "Raise Y-axis ceiling (see peaks)"),
    ("b",          "baseline",      "Snapshot idle baseline (press again to clear)"),
    ("s",          "screenshot",    "Save SVG screenshot to current directory"),
    ("t",          "theme",         "Toggle TacticalCyberpunk ↔ GhostWhite"),
    ("c",          "config",        "Reopen settings wizard (kWh, currency, overhead)"),
    ("*",          "help",          "Show / hide this panel"),
]

_SENSOR_NOTES: list[tuple[str, str]] = [
    ("● REAL",   "Wattage from hardware sensor (hwmon / RAPL / WMI / NVML)"),
    ("◐ MIXED",  "CPU or GPU using estimate; the other is metered"),
    ("◌ EST",    "Estimate only — CPU% × TDP (LHM not running on Windows)"),
    ("⚠ LHM ADMIN", "Windows: LibreHardwareMonitor is not running as Administrator"),
    ("⚠ THROTTLE",  "CPU or GPU clock is < 80 % of boost max"),
    ("◉ BASELINE",  "Baseline snapshot active — delta values shown"),
]


class HelpOverlay(ModalScreen[None]):
    """Full-screen keybinding reference — press ? or Esc to close."""

    DEFAULT_CSS = """
    HelpOverlay {
        align: center middle;
        background: #030507 88%;
    }
    HelpOverlay > #help-card {
        width: 76;
        height: auto;
        max-height: 90%;
        border: double #00aa77;
        background: #060a0e;
        padding: 1 2;
    }
    HelpOverlay #help-title {
        height: 1;
        content-align: center middle;
        color: #00ffcc;
        text-style: bold;
        padding-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        from textual.containers import Vertical
        with Vertical(id="help-card"):
            yield Static("▓░  VIGIL v2.0 — KEYBINDING REFERENCE  ░▓", id="help-title")
            yield Static(self._build_content())

    def _build_content(self) -> Text:
        t = Text()

        # ── Keybindings ────────────────────────────────────────────────────
        t.append("  CONTROLS\n", style="bold #00aa77")
        t.append("  " + "─" * 66 + "\n", style="#0e2030")

        for key, action, desc in _BINDINGS:
            t.append(f"  {key:<18}", style="bold #44ccff")
            t.append(f"  {action:<14}", style="#00cc88")
            t.append(f"  {desc}\n", style="#4a6a7a")

        t.append("\n")

        # ── Sensor quality legend ──────────────────────────────────────────
        t.append("  STATUS BAR BADGES\n", style="bold #00aa77")
        t.append("  " + "─" * 66 + "\n", style="#0e2030")

        for badge, meaning in _SENSOR_NOTES:
            t.append(f"  {badge:<20}", style="bold #ffaa00")
            t.append(f"  {meaning}\n", style="#4a6a7a")

        t.append("\n")

        # ── Quick tips ─────────────────────────────────────────────────────
        t.append("  TIPS\n", style="bold #00aa77")
        t.append("  " + "─" * 66 + "\n", style="#0e2030")
        tips = [
            "Resize terminal < 100 cols → right column hides automatically.",
            "Resize terminal <  80 cols → both side columns hide.",
            "Press  b  twice to clear baseline and return to absolute mode.",
            "vigil exits cleanly — no background daemon is left running.",
            "Config file: ~/.config/vigil/config.toml  (press c to edit live).",
        ]
        for tip in tips:
            t.append("  • ", style="#006644")
            t.append(tip + "\n", style="#3a5060")

        t.append("\n")
        t.append("  Press  *  or  Esc  to close\n", style="#1a3040")

        return t

    def on_key(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.key in ("asterisk", "escape", "q"):
            self.dismiss()
