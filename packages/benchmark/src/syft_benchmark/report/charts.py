"""The charts of the docx report, as PNG bytes.

Every value drawn comes from ``Metrics``: a chart computes nothing of its own,
so a picture cannot diverge from the table beneath it. Figures are built
without ``pyplot``, which keeps global state the background build must not
share.
"""

from __future__ import annotations

import io
from collections.abc import Sequence

from matplotlib.figure import Figure

# The outcome colours are the same across the whole report, one per graded
# verdict, in the order the composition bar stacks them. On the control half
# there is no "correct" at all, and green is absent there not by oversight.
VERDICT_COLOUR: dict[str, str] = {
    "correct": "#2f9e44",
    "abstain": "#f08c00",
    "hallucinate": "#e03131",
    "web_sourced": "#1098ad",
    "incomplete": "#9c36b5",
}

# The sign colours for diverging charts. The sign here is the content: for the
# price of context a minus means "the material helped it abstain", a plus means
# "it removed the caution", and colouring them alike means hiding the conclusion.
GOOD = "#2f9e44"
BAD = "#e03131"
NEUTRAL = "#4c6ef5"

# The height of a bar in inches. A report can have three rows or thirty: a figure
# of fixed height leaves an empty field in the first case and crushes the labels
# in the second.
_ROW = 0.42
_MIN_HEIGHT = 1.6
_WIDTH = 6.4


def _figure(rows: int, *, extra: float = 1.1) -> Figure:
    height = max(_MIN_HEIGHT, rows * _ROW + extra)
    # constrained: the legend caption is moved outside the axes by the layout
    # engine itself. A margin picked by hand is right for exactly the number of
    # rows it was picked at — and a report can have three rows or thirty.
    fig = Figure(figsize=(_WIDTH, height), dpi=200, layout="constrained")
    fig.set_facecolor("white")
    return fig


def _legend(fig: Figure, columns: int) -> None:
    fig.legend(loc="outside lower center", ncols=columns, fontsize=7, frameon=False)


def _png(fig: Figure) -> bytes:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", facecolor="white")
    return buffer.getvalue()


def _style(fig: Figure, title: str) -> None:
    axes = fig.gca()
    axes.set_title(title, fontsize=9, loc="left", pad=8)
    axes.tick_params(labelsize=7)
    axes.spines["top"].set_visible(False)
    axes.spines["right"].set_visible(False)
    axes.grid(axis="x", color="#dee2e6", linewidth=0.5)
    axes.set_axisbelow(True)


def composition(
    labels: Sequence[str],
    parts: Sequence[dict[str, float]],
    *,
    title: str,
) -> bytes:
    """The composition of outcomes: what each row shares are made of.

    The whole bar is all the assessed answers, so it reads not as "where are
    there more correct ones" but as "what the rest is taken up by": an abstention
    and an invention on one bar are told apart at once, and in two separate
    columns they are not.
    """
    fig = _figure(len(labels))
    axes = fig.gca()
    positions = range(len(labels))
    left = [0.0] * len(labels)
    drawn = 0
    for name, colour in VERDICT_COLOUR.items():
        values = [part.get(name, 0.0) for part in parts]
        if not any(values):
            continue
        drawn += 1
        axes.barh(positions, values, left=left, color=colour, label=name, height=0.62)
        for index, (value, start) in enumerate(zip(values, left, strict=True)):
            # A label inside the bar only where it fits: on a share of three
            # percent the text spills onto the neighbouring colour and lies about it.
            if value >= 0.12:
                axes.text(
                    start + value / 2,
                    index,
                    f"{value:.0%}",
                    ha="center",
                    va="center",
                    fontsize=6.5,
                    color="white",
                )
        left = [a + b for a, b in zip(left, values, strict=True)]

    axes.set_yticks(list(positions), labels)
    axes.invert_yaxis()
    axes.set_xlim(0, 1)
    axes.xaxis.set_major_formatter(lambda x, _: f"{x:.0%}")
    _legend(fig, max(1, min(3, drawn)))
    _style(fig, title)
    return _png(fig)


def bars(
    labels: Sequence[str],
    values: Sequence[float],
    *,
    title: str,
    colour: str = NEUTRAL,
    floor: float | None = None,
    floor_label: str = "",
) -> bytes:
    """One quantity by row.

    ``floor`` draws the threshold beyond which the quantity changes meaning:
    consistency below it means the accuracy speaks about which run made it into
    the report rather than about the model. The threshold is on the picture
    rather than in a footnote beneath it, because the conclusion is drawn by eye.
    """
    fig = _figure(len(labels))
    axes = fig.gca()
    positions = range(len(labels))
    # A bar that falls short of the threshold is coloured differently: a
    # threshold is a threshold precisely because the quantity changes meaning
    # beyond it, and the same colour on both sides would make the reader check
    # the bar length against the dashed line by eye.
    colours = (
        [colour if value >= floor else BAD for value in values]
        if floor is not None
        else [colour] * len(values)
    )
    axes.barh(positions, list(values), color=colours, height=0.62)
    for index, value in enumerate(values):
        axes.text(
            value,
            index,
            f" {value:.0%}",
            va="center",
            fontsize=6.5,
            color="#343a40",
        )
    axes.set_yticks(list(positions), labels)
    axes.invert_yaxis()
    axes.set_xlim(0, 1.12)
    axes.xaxis.set_major_formatter(lambda x, _: f"{x:.0%}")
    if floor is not None:
        axes.axvline(floor, color="#868e96", linestyle="--", linewidth=0.9)
        if floor_label:
            # The label inside the field right by the line: the title stands
            # above the axes, and a label moved up there overlaps it the more
            # surely the fewer rows there are.
            axes.text(
                floor,
                0.02,
                f" {floor_label}",
                transform=axes.get_xaxis_transform(),
                fontsize=6.5,
                color="#868e96",
                va="bottom",
            )
    _style(fig, title)
    return _png(fig)


def diverging(
    labels: Sequence[str],
    values: Sequence[float],
    *,
    title: str,
    plus_is_bad: bool = True,
) -> bytes:
    """A signed quantity, laid off from zero in both directions.

    ``plus_is_bad`` switches the colouring: for the price of context a plus is a
    rise in inventions, while for abstention discrimination a plus is the only
    desired outcome. One and the same colour for both cases would mean the colour
    means nothing.
    """
    fig = _figure(len(labels))
    axes = fig.gca()
    positions = range(len(labels))
    colours = [
        (BAD if (value > 0) == plus_is_bad else GOOD) if value else "#adb5bd"
        for value in values
    ]
    axes.barh(positions, list(values), color=colours, height=0.62)
    span = max((abs(v) for v in values), default=0.1) or 0.1
    for index, value in enumerate(values):
        offset = span * 0.03
        axes.text(
            value + (offset if value >= 0 else -offset),
            index,
            f"{value:+.0%}",
            va="center",
            ha="left" if value >= 0 else "right",
            fontsize=6.5,
            color="#343a40",
        )
    axes.set_yticks(list(positions), labels)
    axes.invert_yaxis()
    axes.axvline(0, color="#343a40", linewidth=0.8)
    axes.set_xlim(-span * 1.45, span * 1.45)
    axes.xaxis.set_major_formatter(lambda x, _: f"{x:+.0%}")
    _style(fig, title)
    return _png(fig)


def grouped(
    labels: Sequence[str],
    series: Sequence[tuple[str, Sequence[float | None], str]],
    *,
    title: str,
) -> bytes:
    """Several quantities on one row, side by side.

    Needed where the quantities measure different things and cannot be added into
    one bar: a false abstention is counted against retrieval hits, an answer on a
    miss against misses, and there is no common total for them.

    ``None`` means "not measured" and leaves an empty space. A zero bar cannot be
    drawn in its place: on a picture it is indistinguishable from a measured
    zero, and those are different assertions — "there were no retrieval hits at
    all" and "there were hits, and the model abstained on none of them".
    """
    fig = _figure(len(labels) * len(series), extra=1.2)
    axes = fig.gca()
    count = len(series)
    thickness = 0.72 / count
    for order, (name, values, colour) in enumerate(series):
        offsets = [
            index + (order - (count - 1) / 2) * thickness
            for index in range(len(labels))
        ]
        drawn = [(p, v) for p, v in zip(offsets, values, strict=True) if v is not None]
        if not drawn:
            continue
        axes.barh(
            [p for p, _ in drawn],
            [v for _, v in drawn],
            height=thickness,
            color=colour,
            label=name,
        )
        for position, value in drawn:
            axes.text(
                value,
                position,
                f" {value:.0%}",
                va="center",
                fontsize=6,
                color="#343a40",
            )
    axes.set_yticks(list(range(len(labels))), labels)
    axes.invert_yaxis()
    axes.set_xlim(0, 1.12)
    axes.xaxis.set_major_formatter(lambda x, _: f"{x:.0%}")
    _legend(fig, min(3, count))
    _style(fig, title)
    return _png(fig)
