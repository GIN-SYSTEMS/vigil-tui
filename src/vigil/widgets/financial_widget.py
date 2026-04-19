"""FinancialWidget — live electricity cost display.

Shows cost/hour, cost/day, and cumulative session cost in local currency.
Currency symbol is configurable; defaults to the ₺ (TRY) sign but works
with any single-character symbol.
"""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static


class FinancialWidget(Static):
    """Compact two-line cost readout rendered as a Static."""

    DEFAULT_CSS = """
    FinancialWidget {
        height: 3;
        border-top: solid #0d1a28;
        background: #060810;
        padding: 0 1;
        content-align: left middle;
    }
    """

    def __init__(self, currency: str = "₺", **kwargs: object) -> None:
        super().__init__("", **kwargs)  # type: ignore[arg-type]
        self._currency = currency

    def set_costs(
        self,
        per_hour: float,
        per_day: float,
        session: float,
        session_duration_s: float,
        baseline_delta_w: float | None = None,
    ) -> None:
        cur = self._currency
        t = Text(no_wrap=True)

        t.append("  COST ", style="#0e1828")
        t.append(" /hr ", style="#1a2838")
        t.append(cur, style="#005533")
        t.append(f"{per_hour:6.2f}", style="#00ffcc")

        t.append("   /day ", style="#1a2838")
        t.append(cur, style="#553300")
        t.append(f"{per_day:6.2f}", style="#ffaa00")

        hours = session_duration_s / 3600.0
        t.append(f"   session {hours:.2f}h ", style="#1a2838")
        t.append(cur, style="#004433")
        t.append(f"{session:.4f}", style="bold #00ffcc")

        if baseline_delta_w is not None:
            sign = "+" if baseline_delta_w >= 0 else ""
            color = "#ff3300" if baseline_delta_w > 5 else "#ffaa00" if baseline_delta_w > 0 else "#00cc88"
            t.append(f"   Δ{sign}{baseline_delta_w:.1f}W", style=color)

        self.update(t)
