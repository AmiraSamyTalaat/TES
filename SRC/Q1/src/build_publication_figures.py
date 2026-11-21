from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".python_packages"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np
import pandas as pd

OUT = ROOT / "publication" / "figures"


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def timeline():
    fig, ax = plt.subplots(figsize=(12, 4.2))
    stages = [
        (1988, 1994, "NHANES III\nexternal-era test", "#7a5195"),
        (1999, 2008, "Development", "#2f4b7c"),
        (2009, 2012, "Validation", "#00a6a6"),
        (2013, 2014, "Audit", "#4daf4a"),
        (2015, 2016, "Temporal\nconfirmation", "#f28e2b"),
        (2017, 2018, "Short follow-up\nstress test", "#e15759"),
    ]
    for idx, (start, end, label, color) in enumerate(stages):
        ax.barh(0, end - start + 1, left=start, height=.38, color=color, edgecolor="white")
        midpoint = (start + end) / 2
        if start <= 2013:
            ax.text(midpoint, 0, label, ha="center", va="center", color="white",
                    fontsize=8.5, fontweight="bold")
        elif start == 2015:
            ax.annotate(label, xy=(midpoint, .19), xytext=(midpoint, .42),
                        ha="center", va="bottom", fontsize=8.2, fontweight="bold",
                        arrowprops={"arrowstyle": "-", "color": color, "lw": 1.3})
        else:
            ax.annotate(label, xy=(midpoint, -.19), xytext=(midpoint, -.39),
                        ha="center", va="top", fontsize=8.2, fontweight="bold",
                        arrowprops={"arrowstyle": "-", "color": color, "lw": 1.3})
    ax.axvline(2014.5, color="black", linestyle="--", linewidth=1.2)
    ax.text(2014.5, .61, "Pre-confirmatory freeze", ha="center", va="bottom", fontsize=8.5)
    ax.annotate("Models trained on 1999–2008; NHANES III outcomes opened only after external freeze",
                xy=(2005, -.69), ha="center", va="top", fontsize=8.5, color="#333333")
    ax.set_xlim(1986.5, 2020); ax.set_ylim(-.88, .82); ax.set_yticks([])
    ax.set_xlabel("Survey era / evaluation chronology")
    ax.spines[["left", "right", "top"]].set_visible(False)
    ax.set_title("Study timeline and locked evaluation stages", loc="left", fontweight="bold")
    save(fig, "FIGURE1_STUDY_TIMELINE")


def forest():
    items = [
        ("XGBoost-Cox vs Cox\nValidation 2009–2012", .0121893, .0093164, .0148734),
        ("XGBoost-AFT vs XGBoost-Cox\nValidation 2009–2012", .0013521, .0002044, .0025012),
        ("XGBoost-Cox vs Cox\nTemporal 2015–2016", .0077328, .0027755, .0127700),
        ("XGBoost-Cox vs Cox\nStress test 2017–2018", .0154311, .0068674, .0247000),
        ("Full AFT vs XGBoost-Cox\nExternal NHANES III", -.0003590, -.0009524, .0002430),
        ("TES-11 vs Full AFT\nExternal NHANES III", -.0014444, -.0022050, -.0006802),
    ]
    fig, ax = plt.subplots(figsize=(9, 5.8))
    y = np.arange(len(items))[::-1]
    gains = np.array([x[1] for x in items]); low = np.array([x[2] for x in items]); high = np.array([x[3] for x in items])
    colors = ["#2f4b7c" if g >= 0 else "#e15759" for g in gains]
    for yi, gain, lo, hi, color in zip(y, gains, low, high, colors):
        ax.errorbar(gain, yi, xerr=[[gain - lo], [hi - gain]], fmt="none", ecolor=color, capsize=4, linewidth=1.8)
    ax.scatter(gains, y, c=colors, s=55, zorder=3)
    ax.axvline(0, color="black", linewidth=1, linestyle="--")
    ax.set_yticks(y, [x[0] for x in items]); ax.set_xlabel("Paired C-index difference (95% bootstrap CI)")
    ax.grid(axis="x", alpha=.25); ax.spines[["right", "top"]].set_visible(False)
    ax.set_title("Discrimination differences across chronological and external evaluations", loc="left", fontweight="bold")
    save(fig, "FIGURE2_CINDEX_FOREST")


def shap_heatmap():
    profile = pd.read_csv(ROOT / "outputs" / "temporal_shap_stability" / "cycle_feature_shap_profiles.csv")
    cycles = ["2009-2010", "2011-2012", "2013-2014"]
    mean_importance = profile.groupby("feature")["normalized_importance"].mean().sort_values(ascending=False)
    features = mean_importance.head(11).index.tolist()
    pivot = profile.pivot(index="feature", columns="cycle", values="normalized_importance").loc[features, cycles]
    fig, ax = plt.subplots(figsize=(7.5, 6.2))
    values = pivot.to_numpy()
    positive = values[values > 0]
    norm = LogNorm(vmin=float(positive.min()), vmax=float(positive.max()))
    image = ax.imshow(values, cmap="cividis", norm=norm, aspect="auto")
    ax.set_xticks(range(len(cycles)), cycles); ax.set_yticks(range(len(features)), [f.replace("_", " ") for f in features])
    for i in range(len(features)):
        for j in range(len(cycles)):
            value = pivot.iloc[i, j]
            contrast = norm(value)
            ax.text(j, i, f"{value:.3f}", ha="center", va="center",
                    color="white" if contrast < .34 or contrast > .82 else "black",
                    fontsize=8, fontweight="bold" if i < 2 else "normal")
    fig.colorbar(image, ax=ax, label="Normalized mean |SHAP| (log color scale)")
    ax.set_title("Temporal stability of global SHAP importance", loc="left", fontweight="bold")
    ax.set_xlabel("NHANES cycle"); ax.set_ylabel("Feature")
    save(fig, "FIGURE3_TEMPORAL_SHAP_HEATMAP")


def main() -> int:
    timeline(); forest(); shap_heatmap()
    files = sorted(path.name for path in OUT.iterdir() if path.suffix in {".png", ".pdf"})
    status = {"status": "PASS", "figures": files, "formats": ["PNG 300 dpi", "vector PDF"]}
    (OUT / "FIGURE_BUILD_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
