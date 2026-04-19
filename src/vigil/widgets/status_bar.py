"""StatusBar widget — two-line footer.

Row 1 (identity + sensors):
  OS  ·  arch  ·  uptime  ·  cpu:src  gpu:src  ·  TRUST BADGE  ·  ⏱ ms

Row 2 (keybinding strip):
  [*] help  [c] config  [q] quit  [p] pause  [r] reset  [b] baseline  [t] theme  [+/-] zoom  [s] shot
"""

from __future__ import annotations

import platform
import time

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label

_UNAME = platform.uname()
_SESSION_START = time.monotonic()
_IS_WINDOWS = platform.system() == "Windows"

_SEP = Text("  ·  ", style="#0e1a22")

# Sources we trust as direct hardware reads (vs. CPU% × TDP guesses).
_REAL_SOURCES: frozenset[str] = frozenset({
    "hwmon", "rapl", "wmi", "nvml",
})

_KEY_HINTS = (
    "[*] help",
    "[c] config",
    "[q] quit",
    "[p] pause",
    "[r] reset",
    "[b] baseline",
    "[t] theme",
    "[+/-] zoom",
    "[s] shot",
)


def _uptime() -> str:
    s = int(time.monotonic() - _SESSION_START)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}h {m:02d}m {sec:02d}s"


def _trust_label(cpu_src: str, gpu_src: str) -> tuple[str, str, bool]:
    """Return (icon_text, color, lhm_hint_needed) for the trust badge."""
    cpu_real = cpu_src in _REAL_SOURCES
    gpu_real = gpu_src in _REAL_SOURCES

    if cpu_real and gpu_real:
        return "● REAL", "#00cc88", False
    if not cpu_real and not gpu_real:
        return "◌ EST", "#cc4400", _IS_WINDOWS and cpu_src == "estimate"
    return "◐ MIXED", "#ffaa00", _IS_WINDOWS and cpu_src == "estimate"


class StatusBar(Widget):
    """Two-line footer: OS identity + trust badge (row 1) · key hints (row 2)."""

    DEFAULT_CSS = """
    StatusBar {
        height: 2;
        background: #030507;
        color: #1e2e3a;
        padding: 0 1;
        dock: bottom;
    }
    StatusBar > #status-identity {
        height: 1;
        background: #030507;
        color: #1e2e3a;
    }
    StatusBar > #status-keys {
        height: 1;
        background: #020406;
        color: #0e1a22;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._cpu_src: str = "—"
        self._gpu_src: str = "—"
        self._sample_ms: float = 0.0
        self._cpu_throttled: bool = False
        self._gpu_throttled: bool = False
        self._baseline_active: bool = False
        self._blink_state: bool = False

    def compose(self) -> ComposeResult:
        yield Label("", id="status-identity")
        yield Label("", id="status-keys")

    def update_display(
        self,
        cpu_source: str,
        gpu_source: str,
        sample_ms: float,
        cpu_throttled: bool = False,
        gpu_throttled: bool = False,
        baseline_active: bool = False,
    ) -> None:
        self._cpu_src = cpu_source
        self._gpu_src = gpu_source
        self._sample_ms = sample_ms
        self._cpu_throttled = cpu_throttled
        self._gpu_throttled = gpu_throttled
        self._baseline_active = baseline_active
        self._blink_state = not self._blink_state
        self._refresh_rows()

    def _refresh_rows(self) -> None:
        try:
            self.query_one("#status-identity", Label).update(self._render_identity())
            self.query_one("#status-keys", Label).update(self._render_keys())
        except Exception:
            pass

    def _render_identity(self) -> Text:
        t = Text(no_wrap=True, overflow="ellipsis")

        t.append(f"{_UNAME.system} {_UNAME.release[:16]}", style="#223038")
        t.append_text(_SEP)
        t.append(_UNAME.machine, style="#182430")
        t.append_text(_SEP)
        t.append("up ", style="#0e1820")
        t.append(_uptime(), style="#203038")
        t.append_text(_SEP)
        t.append("cpu:", style="#0e2018")
        t.append(self._cpu_src, style="#1e4830")
        t.append("  gpu:", style="#0e1820")
        t.append(self._gpu_src, style="#1e3048")
        t.append_text(_SEP)

        # Trust badge
        icon, color, lhm_hint = _trust_label(self._cpu_src, self._gpu_src)
        t.append(icon, style=f"bold {color}")
        if lhm_hint:
            t.append("  ⚠ LHM ADMIN", style="bold #ffaa00")

        t.append_text(_SEP)
        t.append(f"⏱ {self._sample_ms:.0f} ms", style="#142028")

        if self._cpu_throttled or self._gpu_throttled:
            src = "CPU" if self._cpu_throttled else "GPU"
            if self._gpu_throttled and self._cpu_throttled:
                src = "CPU+GPU"
            blink_style = "bold #ff3300" if self._blink_state else "bold #661100"
            t.append_text(_SEP)
            t.append(f"⚠ {src} THERMAL THROTTLE", style=blink_style)
        elif self._baseline_active:
            t.append_text(_SEP)
            t.append("◉ BASELINE ACTIVE", style="#00cc88")

        return t

    def _render_keys(self) -> Text:
        t = Text(no_wrap=True, overflow="ellipsis")
        t.append("  ", style="")
        for i, hint in enumerate(_KEY_HINTS):
            if i > 0:
                t.append("  ", style="")
            parts = hint.split("]", 1)
            if len(parts) == 2:
                t.append("[", style="#0e1828")
                t.append(parts[0][1:], style="#1e4060")
                t.append("]", style="#0e1828")
                t.append(parts[1], style="#0e1828")
            else:
                t.append(hint, style="#0e1828")
        return t
