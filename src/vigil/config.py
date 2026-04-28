"""Central configuration — all tunable constants in one place.

Edit CPU_TDP_WATTS / GPU_TDP_WATTS to match your actual hardware.
Everything else can be left at defaults.
"""

# ── Sampling ──────────────────────────────────────────────────────────────
UPDATE_INTERVAL: float = 1.0    # seconds between collector polls
HISTORY_LEN: int = 120          # ring-buffer depth (samples; 120 s at 1 Hz)

# ── TDP ceilings — used for % fallback estimates and chart Y-axis defaults
CPU_TDP_WATTS: float = 65.0     # AMD Ryzen 7 typical TDP
GPU_TDP_WATTS: float = 165.0    # NVIDIA RTX 4000-series typical TDP

# Total system ceiling — CPU + GPU + ~30 W motherboard/storage/fans
SYSTEM_TDP_WATTS: float = CPU_TDP_WATTS + GPU_TDP_WATTS + 30.0

# ── Combined power chart Y-axis ceiling
CHART_COMBINED_Y_MAX: float = max(CPU_TDP_WATTS, GPU_TDP_WATTS)

# ── RAM power model: DDR4 ~3.5 W per 8 GB module, utilisation-scaled
RAM_WATTS_PER_8GB: float = 3.5

# ── Per-core display cap (logical cores). The panel auto-grids and scrolls,
# so this is just an upper bound to keep the render cheap on absurdly large
# core counts. Bumped from 16 in #3 to support 32T+ workstations.
MAX_DISPLAY_CORES: int = 256

# ── Column-count thresholds for the per-core grid.
# Cores are laid out left-to-right, top-to-bottom. The panel picks the
# largest column count whose threshold is <= the system's logical core count.
CPU_GRID_THRESHOLDS: tuple[tuple[int, int], ...] = (
    (1, 1),    # 1+ cores -> 1 column
    (17, 2),   # 17+ cores -> 2 columns
    (33, 3),   # 33+ cores -> 3 columns
    (65, 4),   # 65+ cores -> 4 columns
)

# ── Process table ─────────────────────────────────────────────────────────
PROCESS_TOP_N: int = 10

# System/idle processes to hide from the process table.
PROCESS_FILTER_NAMES: frozenset[str] = frozenset({
    # Windows
    "system idle process", "system", "registry", "smss.exe",
    "csrss.exe", "wininit.exe", "services.exe", "lsass.exe",
    "svchost.exe", "dwm.exe", "fontdrvhost.exe", "sihost.exe",
    "taskhostw.exe", "runtimebroker.exe", "searchindexer.exe",
    "spoolsv.exe", "audiodg.exe", "wudfhost.exe",
    "securityhealthservice.exe", "msmpeng.exe",
    # Linux
    "kthreadd", "migration", "ksoftirqd", "watchdog",
    "kdevtmpfs", "kauditd", "khungtaskd", "kswapd0", "writeback",
    "kcompactd0", "kintegrityd", "idle_inject",
})

# Processes whose name *starts with* any of these prefixes are filtered.
PROCESS_FILTER_PREFIXES: tuple[str, ...] = (
    "kworker/", "irq/", "rcu_", "idle_inject/", "kthread",
)

# ── Braille chart Y-axis ──────────────────────────────────────────────────
# Characters reserved on the left of each BrailleChart for axis labels.
# Format: "  165W┤"  (5 digit-chars + "W" + "┤" = 7 total)
CHART_Y_AXIS_W: int = 7
