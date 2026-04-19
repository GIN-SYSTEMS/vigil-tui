"""SetupWizard — first-run modal that captures cost/overhead settings.

Shown once when ``load_config()`` reports ``is_first_run == True``.  Writes
the user's answers back into ``~/.config/vigil/config.toml`` via
``save_user_settings()`` so subsequent launches skip the wizard entirely.

Design goals:
  * Keep the question count small (3 fields) — this is a power-user tool
    and a long onboarding form would be annoying.
  * On Windows, surface the LibreHardwareMonitor admin requirement up
    front rather than letting the user discover later that CPU wattage
    is being estimated.
  * Allow ``Skip`` so users who don't care about cost can dismiss the
    wizard with sensible defaults pre-filled in config.toml.
"""

from __future__ import annotations

import platform
from dataclasses import replace

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from vigil.config_manager import AppConfig, save_user_settings

_IS_WINDOWS = platform.system() == "Windows"


class SetupWizard(ModalScreen[AppConfig]):
    """First-run modal — collects kWh price, currency, system overhead."""

    DEFAULT_CSS = """
    SetupWizard {
        align: center middle;
        background: #030507 92%;
    }
    SetupWizard > #wizard-card {
        width: 64;
        height: auto;
        max-height: 90%;
        border: double #00aa77;
        background: #060a0e;
        padding: 1 2;
    }
    SetupWizard #wizard-title {
        height: 1;
        content-align: center middle;
        color: #00ffcc;
        text-style: bold;
    }
    SetupWizard #wizard-blurb {
        height: auto;
        color: #4a6070;
        padding: 1 0;
    }
    SetupWizard .field-label {
        height: 1;
        color: #00aa77;
        text-style: bold;
        padding-top: 1;
    }
    SetupWizard .field-help {
        height: 1;
        color: #2a4050;
    }
    SetupWizard Input {
        height: 3;
        background: #0a1018;
        color: #c4cdd8;
        border: tall #143040;
    }
    SetupWizard Input:focus {
        border: tall #00aa77;
    }
    SetupWizard #lhm-warning {
        height: auto;
        background: #1a1408;
        color: #ffaa00;
        padding: 1;
        margin-top: 1;
        border-left: thick #ffaa00;
    }
    SetupWizard #button-row {
        height: 3;
        align: center middle;
        padding-top: 1;
    }
    SetupWizard Button {
        margin: 0 1;
    }
    SetupWizard #save-btn {
        background: #006644;
        color: #00ffcc;
    }
    SetupWizard #skip-btn {
        background: #1a2030;
        color: #6a7a8a;
    }
    """

    def __init__(self, current: AppConfig, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._current = current

    def compose(self) -> ComposeResult:
        with Vertical(id="wizard-card"):
            yield Label("▓░ VIGIL — FIRST-RUN SETUP ░▓", id="wizard-title")
            yield Static(
                Text.from_markup(
                    "Three quick questions so the cost readout reflects your "
                    "actual setup. You can edit these later in [bold "
                    "#00aa77]~/.config/vigil/config.toml[/]."
                ),
                id="wizard-blurb",
            )

            yield Label("Electricity price per kWh", classes="field-label")
            yield Label("(check your latest electricity bill)", classes="field-help")
            yield Input(
                value=f"{self._current.kwh_price:g}",
                id="kwh-input",
                placeholder="4.5",
            )

            yield Label("Currency symbol", classes="field-label")
            yield Label("(any single character — ₺, $, €, £, ₹, ¥)", classes="field-help")
            yield Input(
                value=self._current.currency_symbol,
                id="currency-input",
                placeholder="\u20ba",
                max_length=4,
            )

            yield Label("System overhead watts", classes="field-label")
            yield Label(
                "(motherboard + SSDs + fans + USB; ~30 W is typical)",
                classes="field-help",
            )
            yield Input(
                value=f"{self._current.system_overhead_watts:g}",
                id="overhead-input",
                placeholder="30",
            )

            if _IS_WINDOWS:
                yield Static(
                    Text.from_markup(
                        "[bold]⚠ Windows note[/]\n"
                        "For accurate CPU wattage, launch "
                        "[bold]LibreHardwareMonitor as Administrator[/] "
                        "before vigil. Otherwise CPU readings fall back to "
                        "[bold]CPU% × TDP[/] (look for ◌ EST in status bar)."
                    ),
                    id="lhm-warning",
                )

            with Horizontal(id="button-row"):
                yield Button("Save & Continue", id="save-btn", variant="success")
                yield Button("Skip", id="skip-btn")

    # ── Event handlers ─────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self._save_and_dismiss()
        elif event.button.id == "skip-btn":
            self.dismiss(self._current)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Pressing Enter from any input triggers save.
        self._save_and_dismiss()

    def on_key(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.key == "escape":
            self.dismiss(self._current)

    # ── Persistence ────────────────────────────────────────────────────────

    def _save_and_dismiss(self) -> None:
        kwh = self._safe_float("kwh-input", self._current.kwh_price, lo=0.0, hi=1000.0)
        currency = (
            self.query_one("#currency-input", Input).value.strip()
            or self._current.currency_symbol
        )
        overhead = self._safe_float(
            "overhead-input",
            self._current.system_overhead_watts,
            lo=0.0,
            hi=500.0,
        )

        try:
            save_user_settings(
                kwh_price=kwh,
                currency_symbol=currency[:4],
                system_overhead_watts=overhead,
            )
        except Exception:
            # Don't trap the user in the wizard if disk write fails — just
            # apply in-memory and continue.
            pass

        new_cfg = replace(
            self._current,
            kwh_price=kwh,
            currency_symbol=currency[:4],
            system_overhead_watts=overhead,
        )
        self.dismiss(new_cfg)

    def _safe_float(self, widget_id: str, fallback: float, *, lo: float, hi: float) -> float:
        raw = self.query_one(f"#{widget_id}", Input).value.strip().replace(",", ".")
        try:
            v = float(raw)
        except ValueError:
            return fallback
        return max(lo, min(hi, v))
