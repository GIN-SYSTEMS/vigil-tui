# vigil

> Real-time terminal power monitor — CPU · GPU · RAM · Network · Process load

A high-resolution TUI dashboard that shows live wattage, thermals, efficiency scores, and electricity cost for your system — all inside the terminal.

```
▓░ VIGIL ░▓   ████████████░░░░░░░░░░░░░░░░    18.8 W / 260 W  [cpu:estimate  gpu:nvml]
```

---

## Features

- **CPU power** — hwmon (AMD/Intel) · RAPL · LibreHardwareMonitor · estimate fallback
- **GPU power** — NVIDIA via NVML; temperature, VRAM, clocks, fan
- **RAM wattage** — DDR4 power model (slot count × utilisation)
- **Per-core bars** — utilisation + frequency with boost detection
- **Power history chart** — high-resolution Braille overlay (CPU + GPU)
- **Process ranking** — top processes by estimated wattage with sparklines
- **Electricity cost** — ₺/hr, ₺/day, session total (configurable currency)
- **Throttle detection** — visual blinking alert when CPU or GPU is throttled
- **Efficiency score** — perf/watt rating: OPTIMAL · NORMAL · LOW EFF · THROTTLE
- **Baseline mode** — snapshot idle state, compare deltas in real time
- **Webhook alerts** — HTTP POST on CPU temp or power threshold breach
- **Session logging** — optional JSONL tick log (`--log` flag)
- **Two themes** — TacticalCyberpunk (dark) · GhostWhite (light)

---

## Platform Support

| Platform | CPU Power | GPU Power | Temperature |
|----------|-----------|-----------|-------------|
| **Linux** | hwmon · RAPL · estimate | NVML | hwmon |
| **Windows 11/10** | LibreHardwareMonitor · estimate | NVML | LHM |
| **macOS** | estimate only | estimate only | — |

### Windows Note
For accurate CPU readings on Windows, run [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) as Administrator before launching vigil. Without it, vigil falls back to CPU% × TDP estimation.

---

## Installation

**Requirements:** Python 3.11+

```bash
# Clone
git clone https://github.com/yourusername/vigil
cd vigil

# Install (Linux / macOS)
pip install .

# Install (Windows — includes WMI + pywin32)
pip install ".[windows]"
```

**Run:**
```bash
vigil          # launch dashboard
vigil --log    # launch + write JSONL tick log
```

---

## Key Bindings

| Key | Action |
|-----|--------|
| `q` / Ctrl+C | Quit |
| `p` | Pause / resume sampling |
| `r` | Reset chart history |
| `+` / `-` | Zoom Y-axis in / out |
| `b` | Snapshot baseline (press again to clear) |
| `s` | Save SVG screenshot |
| `t` | Toggle theme (dark ↔ light) |

---

## Configuration

On first launch, vigil creates `~/.config/vigil/config.toml`:

```toml
cpu_tdp_watts     = 65.0       # your CPU's TDP ceiling
gpu_tdp_watts     = 165.0      # your GPU's TDP ceiling
update_interval   = 1.0        # seconds between ticks
history_len       = 120        # chart ring-buffer depth
kwh_price         = 2.0        # electricity price per kWh
webhook_url       = ""         # optional alert endpoint
cpu_temp_thresh   = 90         # °C alert threshold
cpu_watt_thresh_pct = 90       # % of TDP alert threshold
theme             = "tactical" # "tactical" or "ghost"
```

---

## Project Structure

```
src/vigil/
├── app.py               # Main Textual app, layout, tick loop
├── config.py            # Static constants
├── config_manager.py    # TOML config loader
├── session.py           # Cost tracking, alerts, logging
├── collectors/
│   ├── cpu.py           # CPU power (hwmon → RAPL → LHM → estimate)
│   ├── gpu.py           # NVIDIA NVML
│   ├── ram.py           # RAM power model
│   ├── netdisk.py       # Net + disk I/O rates
│   └── system.py        # Orchestrator, snapshot types
└── widgets/
    ├── power_header.py  # Top bar: wordmark + gauge
    ├── cpu_panel.py     # Left: CPU metrics + per-core
    ├── braille_chart.py # Center: high-res power history
    ├── process_table.py # Center: process ranking
    ├── gpu_panel.py     # Right: GPU metrics
    ├── financial_widget.py  # Cost display
    ├── netdisk_widget.py    # Net + disk rates
    ├── status_bar.py        # Footer
    └── boot_screen.py       # Splash screen
```

---

## License

[MIT](LICENSE)
