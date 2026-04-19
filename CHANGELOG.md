# Changelog

All notable changes to vigil are documented here.

Format: [Semantic Versioning](https://semver.org/). Categories: `Added`, `Changed`, `Fixed`, `Removed`.

---

## [1.0.0] — 2025

### Added
- Initial public release
- Real-time CPU power: hwmon (AMD/Intel), RAPL, LibreHardwareMonitor, estimate fallback
- GPU power via NVIDIA NVML: watts, temperature, utilisation, VRAM, clocks, fan
- RAM wattage estimation (DDR4 power model)
- Per-core CPU utilisation bars with frequency and boost detection
- High-resolution Braille area chart (CPU + GPU power overlay)
- Process table ranked by estimated wattage with sparkline trends
- Electricity cost display (configurable kWh price and currency)
- Throttle detection for CPU and GPU with blinking status badge
- Efficiency score: OPTIMAL · NORMAL · LOW EFF · THROTTLE
- Baseline snapshot mode (compare current vs idle delta)
- Webhook alerts on CPU temperature or power threshold breach
- Optional JSONL session logging (`--log` flag)
- Two themes: TacticalCyberpunk (dark) and GhostWhite (light)
- TOML configuration file at `~/.config/vigil/config.toml`
- Key bindings: pause, reset, zoom, baseline, screenshot, theme toggle
- SVG screenshot export

### Platform support
- Linux: hwmon, RAPL, NVML
- Windows 11 / Windows 10: LibreHardwareMonitor WMI, NVML
- macOS: estimate fallback, NVML (if available)
