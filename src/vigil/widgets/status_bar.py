"""StatusBar widget — single-line system identity footer.

V3.0: blinking ⚠ THERMAL THROTTLE badge when CPU or GPU is throttling.
"""

from __future__ import annotations

import platform
import time

from rich.text import Text
from textual.widget import Widget

_UNAME = platform.uname()
_SESSION_START = time.monotonic()

_SEP = Text("  ·  ", style="#0e1a22")


def _uptime() -> str:
    s = int(time.monotonic() - _SESSION_START)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}h {m:02d}m {sec:02d}s"


class StatusBar(Widget):
    """Single-line footer: OS identity, sensor sources, sample latency."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: #030507;
        color: #1e2e3a;
        padding: 0 1;
        dock: bottom;
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
        self.refresh()

    def render(self) -> Text:
        t = Text(no_wrap=True, overflow="ellipsis")

        t.append(f"{_UNAME.system} {_UNAME.release[:16]}", style="#223038")
        t.append_text(_SEP)
        t.append(_UNAME.machine, style="#182430")
        t.append_text(_SEP)
        t.append(_UNAME.node[:24], style="#182430")
        t.append_text(_SEP)
        t.append("up ", style="#0e1820")
        t.append(_uptime(), style="#203038")
        t.append_text(_SEP)
        t.append("cpu:", style="#0e2018")
        t.append(self._cpu_src, style="#1e4830")
        t.append("  gpu:", style="#0e1820")
        t.append(self._gpu_src, style="#1e3048")
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
