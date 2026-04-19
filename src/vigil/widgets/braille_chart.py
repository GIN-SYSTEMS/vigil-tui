"""High-resolution Braille area chart with Y-axis and reference grid.

Rendering pipeline (one terminal row at a time via render_line):

  ┌─────────┬──────────────────────────────────────────┐
  │  165W┤  │⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿│  ← reference row
  │        ┊ │⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿         │
  │  124W┤  │⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌│  ← grid line
  │        ┊ │⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿                    │
  │   82W┤  │╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌│  ← grid line (no data)
  │        ┊ │                                  │
  │   41W┤  │                                  │  ← grid line
  │        ┊ │                                  │
  │    0W┤  │                                  │  ← grid line (bottom)
  └─────────┴──────────────────────────────────┘
  ← Y_AXIS_W → ←────── chart area ──────────────→

Unicode Braille bit layout (standard eight-dot, ISO 11548-1):

  pixel col →   0       1
  pixel row 0   0x01    0x08
  pixel row 1   0x02    0x10
  pixel row 2   0x04    0x20
  pixel row 3   0x40    0x80

Each terminal cell encodes a 2×4 pixel grid.  A 80-col × 20-row widget
has 160 × 80 effective pixels after subtracting the Y-axis columns.

Supports up to 2 overlaid series (different colours; overlap → neutral).
"""

from __future__ import annotations

from collections import deque
from typing import Sequence

from rich.segment import Segment
from rich.style import Style
from textual.strip import Strip
from textual.widget import Widget

from vigil import config

# Braille bit values: _BITS[pixel_row][pixel_col_in_cell]
_BITS: list[list[int]] = [
    [0x01, 0x08],
    [0x02, 0x10],
    [0x04, 0x20],
    [0x40, 0x80],
]

# Character drawn on grid-reference rows where a cell has no data.
_GRID_CHAR = "╌"
_GRID_STYLE = Style(color="#111c28")

# Y-axis label and separator styles.
_AXIS_LABEL_STYLE = Style(color="#2a4a5a")
_AXIS_SEP_STYLE = Style(color="#0d1a28")

# Fraction values where horizontal reference lines are drawn.
_REF_FRACS = (1.0, 0.75, 0.5, 0.25, 0.0)


class BrailleChart(Widget):
    """Filled-area Braille chart with labelled Y-axis and reference grid.

    Parameters
    ----------
    y_max:
        Y-axis ceiling in watts.  Adjustable at runtime via ``set_y_max()``.
    history_len:
        Ring-buffer depth (number of samples retained).
    series_colors:
        One Rich colour string per data series.  Pass two for CPU+GPU overlay.
    """

    DEFAULT_CSS = """
    BrailleChart {
        height: 1fr;
        background: #090d12;
    }
    """

    def __init__(
        self,
        *,
        y_max: float = 100.0,
        history_len: int = 120,
        series_colors: Sequence[str] = ("#00ccaa",),
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.y_max = max(1.0, y_max)
        self._colors = list(series_colors)
        self._series: list[deque[float]] = [
            deque([0.0] * history_len, maxlen=history_len)
            for _ in series_colors
        ]

    # ── Public API ─────────────────────────────────────────────────────────

    def push(self, series_index: int, value: float) -> None:
        """Append *value* (watts) to series *series_index* and refresh."""
        if 0 <= series_index < len(self._series):
            self._series[series_index].append(max(0.0, value))
        self.refresh()

    def set_y_max(self, y_max: float) -> None:
        """Adjust the Y-axis ceiling and redraw."""
        self.y_max = max(1.0, y_max)
        self.refresh()

    def reset(self) -> None:
        """Clear all series history."""
        for s in self._series:
            maxlen = s.maxlen or 120
            s.clear()
            s.extend([0.0] * maxlen)
        self.refresh()

    # ── Textual rendering ──────────────────────────────────────────────────

    def render_line(self, y: int) -> Strip:
        """Render terminal row *y* as a Strip of Braille + Y-axis segments."""
        width = self.size.width
        height = self.size.height
        ax_w = config.CHART_Y_AXIS_W        # chars reserved for axis
        chart_w = width - ax_w

        if chart_w <= 0 or height == 0:
            return Strip([Segment(" " * max(width, 1))])

        # Which terminal rows carry reference lines?
        ref_map = self._build_ref_map(height)
        is_ref = y in ref_map

        # ── Y-axis segment (ax_w chars) ────────────────────────────────
        if is_ref:
            _, ref_watts = ref_map[y]
            label = f"{ref_watts:5.0f}W┤"     # e.g. "  165W┤"
            axis_seg = Segment(label, _AXIS_LABEL_STYLE)
        else:
            axis_seg = Segment("      ┊", _AXIS_SEP_STYLE)

        # ── Chart area (chart_w chars = chart_w*2 pixel columns) ───────
        px_h = height * 4
        px_w = chart_w * 2
        pr_start = y * 4          # first pixel row of this terminal row

        cell_bits = [0] * chart_w
        cell_owner = [0] * chart_w    # bitmask: bit i → series i active

        for s_idx, series in enumerate(self._series):
            data = list(series)
            n = len(data)
            if n == 0:
                continue

            for px_col in range(px_w):
                data_idx = n - px_w + px_col     # right-aligned; newest = right
                if data_idx < 0 or data_idx >= n:
                    continue

                val = data[data_idx]
                if val <= 0.0:
                    continue

                norm = min(val / self.y_max, 1.0)
                # Topmost filled pixel row (0 = screen top).
                fill_top = px_h - 1 - int(norm * (px_h - 1))

                tc = px_col >> 1       # terminal column
                bc = px_col & 1        # braille column (0=left, 1=right)

                for pr_off in range(4):
                    if pr_start + pr_off >= fill_top:
                        cell_bits[tc] |= _BITS[pr_off][bc]
                        cell_owner[tc] |= (1 << s_idx)

        # ── Assemble segments ──────────────────────────────────────────
        segs: list[Segment] = [axis_seg]
        n_series = len(self._colors)
        both_mask = (1 << n_series) - 1

        for col in range(chart_w):
            bits = cell_bits[col]
            owner = cell_owner[col]

            if bits == 0:
                # Empty cell: draw grid character on reference rows.
                segs.append(Segment(_GRID_CHAR if is_ref else " ", _GRID_STYLE if is_ref else None))
                continue

            ch = chr(0x2800 + bits)

            if n_series > 1 and owner == both_mask:
                style = Style(color="#c4cdd8")       # overlap → neutral light
            elif owner & 1:
                style = Style(color=self._colors[0])
            else:
                style = Style(color=self._colors[1] if n_series > 1 else self._colors[0])

            segs.append(Segment(ch, style))

        return Strip(segs)

    # ── Internal helpers ───────────────────────────────────────────────────

    def _build_ref_map(self, height: int) -> dict[int, tuple[float, float]]:
        """Map terminal row → (fraction, watts) for each reference line.

        Uses the minimum number of refs that fit without collision.
        """
        fracs = _REF_FRACS if height >= 5 else (1.0, 0.0)
        result: dict[int, tuple[float, float]] = {}
        for frac in fracs:
            row = height - 1 - int(frac * (height - 1))
            row = max(0, min(height - 1, row))
            if row not in result:   # first write wins on collision
                result[row] = (frac, frac * self.y_max)
        return result
