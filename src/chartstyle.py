"""Chart theme used by the build scripts: white canvas, no top or right spines, light grid."""
import matplotlib as mpl

C = {"primary": "#0f62fe", "ink": "#161616", "ink_mut": "#525252", "ink_sub": "#8c8c8c",
     "canvas": "#ffffff", "hairline": "#e0e0e0"}


def apply():
    mpl.rcParams.update({
        "figure.facecolor": C["canvas"], "axes.facecolor": C["canvas"], "savefig.facecolor": C["canvas"],
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans", "Helvetica Neue", "Arial", "sans-serif"],
        "font.size": 10, "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.titlepad": 12, "axes.labelsize": 10, "axes.labelcolor": C["ink_mut"],
        "axes.edgecolor": C["hairline"], "axes.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False,
        "text.color": C["ink"], "xtick.color": C["ink_sub"], "ytick.color": C["ink_sub"],
        "xtick.labelsize": 9, "ytick.labelsize": 9,
        "grid.color": C["hairline"], "grid.linewidth": 0.7, "axes.axisbelow": True,
        "axes.grid": True, "axes.grid.axis": "y",
    })


def save(fig, path, dpi=200):
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor=C["canvas"])
    return path
