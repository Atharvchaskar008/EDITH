"""Shared look for every chart in this pack (matplotlib, written to PNG).

Colours follow one fixed order and always mean the same thing; the order was
checked for colour-blind separation. Text is never drawn in a series colour.
"""

from __future__ import annotations

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SURFACE, INK, INK_SOFT, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]

# one colour per kind of object, the same in every chart
GROUP_ORDER = ["STARLINK", "ACTIVE_OTHER", "IRIDIUM_NEXT", "DEAD_PAYLOAD", "ROCKET_BODY", "DEBRIS"]
GROUP_COLOUR = dict(zip(GROUP_ORDER, SERIES))
GROUP_LABEL = {
    "STARLINK": "Starlink", "ACTIVE_OTHER": "Other working satellites", "IRIDIUM_NEXT": "Iridium NEXT",
    "DEAD_PAYLOAD": "Dead satellites", "ROCKET_BODY": "Rocket bodies", "DEBRIS": "Debris",
}


def figure(columns: int = 1, width: float = 6.4, height: float = 4.2, **kwargs):
    fig, axes = plt.subplots(1, columns, figsize=(width * columns if columns > 1 else width, height),
                             facecolor=SURFACE, **kwargs)
    for ax in ([axes] if columns == 1 else list(axes)):
        style(ax)
    return fig, axes


def style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK_SOFT, labelsize=9, length=0)
    ax.title.set_color(INK)
    ax.xaxis.label.set_color(INK_SOFT)
    ax.yaxis.label.set_color(INK_SOFT)


def titled(ax, title: str, xlabel: str = "", ylabel: str = "") -> None:
    ax.set_title(title, fontsize=10.5, loc="left", color=INK, fontweight="bold")
    ax.set_xlabel(xlabel, fontsize=9, color=INK_SOFT)
    ax.set_ylabel(ylabel, fontsize=9, color=INK_SOFT)


def legend(target, **kwargs) -> None:
    box = target.legend(frameon=False, fontsize=8.5, labelcolor=INK_SOFT, **kwargs)
    return box


def save(fig, path) -> None:
    fig.savefig(path, dpi=160, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
