"""Boot animation — full-screen splash overlay shown for ~1.5 seconds on launch."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static

_LOGO_LINES = [
    r" ██╗   ██╗██╗ ██████╗ ██╗██╗     ",
    r" ██║   ██║██║██╔════╝ ██║██║     ",
    r" ██║   ██║██║██║  ███╗██║██║     ",
    r" ╚██╗ ██╔╝██║██║   ██║██║██║     ",
    r"  ╚████╔╝ ██║╚██████╔╝██║███████╗",
    r"   ╚═══╝  ╚═╝ ╚═════╝ ╚═╝╚══════╝",
]

_ACCENT_LINES = [
    "  ┌─────────────────────────────────────────────┐",
    "  │  REAL-TIME SYSTEM POWER MONITOR  ·  v1.0    │",
    "  │  CPU · GPU · RAM · NETWORK · PROCESS LOAD   │",
    "  └─────────────────────────────────────────────┘",
    "",
    "              press any key to begin",
]

# Gradient: dimmer → brighter teal per logo row
_ROW_COLORS = ["#004433", "#006644", "#009966", "#00cc99", "#00ffcc", "#00ffdd"]


class BootScreen(ModalScreen[None]):
    """Full-screen ASCII splash, auto-dismissed after 1.5 s."""

    DEFAULT_CSS = """
    BootScreen {
        align: center middle;
        background: #030507 88%;
    }
    BootScreen > Static {
        width: auto;
        height: auto;
        content-align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        t = Text(no_wrap=True, justify="center")
        t.append("\n\n")
        for i, line in enumerate(_LOGO_LINES):
            color = _ROW_COLORS[min(i, len(_ROW_COLORS) - 1)]
            bold = i >= 3
            style = f"bold {color}" if bold else color
            t.append(line + "\n", style=style)
        t.append("\n")
        for i, line in enumerate(_ACCENT_LINES):
            if i in (0, 3):
                t.append(line + "\n", style="#005533")
            elif i == 5:
                t.append(line + "\n", style="#1a3a30")
            else:
                t.append(line + "\n", style="#007755")
        t.append("\n")
        yield Static(t)

    def on_mount(self) -> None:
        self._closed = False
        self.set_timer(1.5, self._close)

    def on_key(self) -> None:
        self._close()

    def _close(self) -> None:
        if not self._closed:
            self._closed = True
            self.dismiss()
