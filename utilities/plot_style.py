"""MATLAB look for the Python figures, so that they can be compared 1:1 with the figures of the original toolbox.

The MATLAB toolbox uses MATLAB's factory defaults (there is no groot / Default* setting anywhere) plus LaTeX for the
axis labels. This module reproduces those defaults in matplotlib:

* apply_matlab_style()  sets rcParams (fonts, line weights, tick direction, legend frame, colour order, no grid, ...);
* style_figure(fig)     applies what rcParams cannot express to a finished figure (serif LaTeX-like axis labels and
                        titles, MATLAB-like tick spacing).

Tick labels, legends and colorbar ticks are set in Arial (MATLAB's Helvetica), axis labels, panel titles and colorbar
labels in Computer Modern (MATLAB's 'Latex' interpreter). Set ``globals.matlab_style = False`` before importing
utilities.plot_utils to keep matplotlib's own look.
"""
import warnings

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import AutoLocator, FuncFormatter, MaxNLocator, ScalarFormatter

# MATLAB's default colour order (get(groot,'defaultAxesColorOrder'))
MATLAB_COLORS = [
    (0.0000, 0.4470, 0.7410),
    (0.8500, 0.3250, 0.0980),
    (0.9290, 0.6940, 0.1250),
    (0.4940, 0.1840, 0.5560),
    (0.4660, 0.6740, 0.1880),
    (0.3010, 0.7450, 0.9330),
    (0.6350, 0.0780, 0.1840),
]

LABEL_FONT = "cmr10"        # Computer Modern Roman: what MATLAB's Latex interpreter draws


def _installed(name):
    try:
        return font_manager.findfont(name, fallback_to_default=False) is not None
    except (ValueError, RuntimeError):
        return False


def apply_matlab_style():
    """Set matplotlib's rcParams to MATLAB's factory defaults (10 pt axes font, 0.5 pt lines, inward ticks, ...)."""
    sans = [f for f in ("Arial", "Helvetica", "Liberation Sans", "DejaVu Sans") if f == "DejaVu Sans" or _installed(f)]
    mpl.rcParams.update({
        # fonts
        "font.family": "sans-serif",
        "font.sans-serif": sans,
        "font.size": 10,
        "axes.labelsize": 11,           # MATLAB: LabelFontSizeMultiplier 1.1
        "axes.titlesize": 11,           # MATLAB: TitleFontSizeMultiplier 1.1
        "axes.titleweight": "normal",
        "axes.labelweight": "normal",
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 9,
        "mathtext.fontset": "cm",       # Latex-like math in labels
        "axes.unicode_minus": False,    # MATLAB draws '-' (hyphen) in tick labels
        # lines and axes
        "lines.linewidth": 0.5,
        "lines.markersize": 6,
        "lines.markeredgewidth": 0.5,          # MATLAB marker lines are as thin as the lines
        "lines.scale_dashes": False,            # MATLAB dash lengths do not depend on the line width
        "lines.dashed_pattern": [4.5, 3.0],
        "axes.linewidth": 0.5,
        "axes.grid": False,
        "axes.prop_cycle": mpl.cycler(color=MATLAB_COLORS),
        "axes.facecolor": "white",
        "axes.edgecolor": "black",      # MATLAB axes are black
        "axes.xmargin": 0,
        "axes.ymargin": 0,
        "axes.autolimit_mode": "round_numbers",   # MATLAB rounds automatic limits to the tick steps
        # ticks: inward, on all four sides (box on)
        "xtick.direction": "in", "ytick.direction": "in",
        "xtick.top": True, "ytick.right": True,
        "xtick.major.size": 3, "ytick.major.size": 3,
        "xtick.major.width": 0.5, "ytick.major.width": 0.5,
        "xtick.minor.size": 1.5, "ytick.minor.size": 1.5,
        "xtick.minor.width": 0.5, "ytick.minor.width": 0.5,
        "xtick.color": "black", "ytick.color": "black",
        # legend: black square frame, opaque
        "legend.frameon": True,
        "legend.edgecolor": "black",
        "legend.fancybox": False,
        "legend.framealpha": 1.0,
        "legend.borderpad": 0.4,
        "legend.handlelength": 2.5,
        # grid (when a figure asks for one, MATLAB's is light grey)
        "grid.color": "0.15",
        "grid.alpha": 0.15,
        "grid.linewidth": 0.5,
        # images / figure
        "image.interpolation": "nearest",
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
    })


def _matlab_tick_label(value, _pos=None):
    """MATLAB prints each tick with as many digits as it needs: -1, -0.5, 0, 0.5, 1 (matplotlib pads to -1.0, 0.0)."""
    text = f"{value:.10g}"
    return "0" if text in ("-0", "0") else text


def _serif(text_obj):
    text_obj.set_fontfamily(LABEL_FONT)


def style_figure(fig):
    """MATLAB touches that rcParams cannot express. Idempotent, safe to call several times."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for ax in fig.axes:
            _serif(ax.xaxis.label)
            _serif(ax.yaxis.label)
            _serif(ax.title)
            _serif(ax._left_title)
            _serif(ax._right_title)
            # MATLAB picks tick steps of 1, 2, 5, 10 (matplotlib also offers 2.5) and prints '%g'-like labels
            for axis in (ax.xaxis, ax.yaxis):
                if axis.get_scale() != "linear":
                    continue
                if type(axis.get_major_locator()) is AutoLocator:
                    axis.set_major_locator(MaxNLocator(nbins="auto", steps=[1, 2, 5, 10]))
                if type(axis.get_major_formatter()) is ScalarFormatter and not getattr(axis, "_keep_formatter", False):
                    axis.set_major_formatter(FuncFormatter(_matlab_tick_label))
        for text in fig.texts:                      # fig.suptitle / fig.text
            _serif(text)
        if fig._suptitle is not None:
            _serif(fig._suptitle)


def color_yyaxis(ax_left, ax_right, color_left, color_right):
    """MATLAB yyaxis: each y axis takes the colour of its line (tick marks, tick labels and axis label)."""
    for ax, color in ((ax_left, color_left), (ax_right, color_right)):
        if ax is not None:
            ax.tick_params(axis="y", colors=color)
            ax.yaxis.label.set_color(color)


def latex_legend(legend):
    """MATLAB legends created with 'Interpreter','Latex' are typeset in Computer Modern."""
    for text in legend.get_texts():
        text.set_fontfamily(LABEL_FONT)
    return legend
