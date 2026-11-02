"""charts.py - every chart in the app, styled to match the interface."""
import numpy as np
import pandas as pd
import seaborn as sns
import plotly.express as px
from matplotlib.figure import Figure

INK = "#2d3436"
ACCENT = "#6c5ce7"
GREEN = "#00b894"
RED = "#e17055"
PALETTE = ["#6c5ce7", "#00b894", "#fdcb6e", "#e17055", "#0984e3", "#fd79a8"]


def _expenses(df):
    return df[df["Type"] == "Expense"]


def _tidy(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#cfd4e3")
    ax.tick_params(colors="#636e72", labelsize=9)
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)


# ================================ drawing functions ==========================
def _draw_monthly(ax, df):
    g = (df.pivot_table(index="Month", columns="Type", values="Amount", aggfunc="sum")
           .reindex(columns=["Income", "Expense"]).fillna(0))
    x = np.arange(len(g))
    w = 0.38
    ax.bar(x - w / 2, g["Income"], w, label="Income", color=GREEN)
    ax.bar(x + w / 2, g["Expense"], w, label="Expense", color=RED)
    ax.set_xticks(x)
    ax.set_xticklabels(pd.to_datetime(g.index).strftime("%b %y"))
    ax.set_title("Income vs Expense", loc="left", fontweight="bold", color=INK)
    ax.set_ylabel("Amount (\u20b9)")
    ax.legend(frameon=False)
    _tidy(ax)


def _draw_donut(ax, df):
    exp = _expenses(df).groupby("Category")["Amount"].sum().sort_values(ascending=False)
    ax.pie(exp.values, labels=exp.index, autopct="%1.0f%%", startangle=90,
           colors=PALETTE, pctdistance=0.78, textprops={"fontsize": 9},
           wedgeprops={"width": 0.45, "edgecolor": "white"})
    ax.text(0, 0, f"\u20b9{exp.sum():,.0f}\nspent", ha="center", va="center",
            fontsize=12, fontweight="bold", color=INK)
    ax.set_title("Where the money goes", loc="left", fontweight="bold", color=INK)


def _draw_balance(ax, df):
    daily = df.sort_values("Date").groupby("Date")["Signed"].sum().cumsum()
    ax.plot(daily.index, daily.values, color=ACCENT, linewidth=2.2)
    ax.fill_between(daily.index, daily.values, alpha=0.15, color=ACCENT)
    ax.set_title("Balance over time", loc="left", fontweight="bold", color=INK)
    ax.set_ylabel("Balance (\u20b9)")
    ax.tick_params(axis="x", labelrotation=20)
    _tidy(ax)


def _draw_hist(ax, df):
    amounts = _expenses(df)["Amount"]
    ax.hist(amounts, bins=15, color=ACCENT, edgecolor="white", alpha=0.9)
    ax.axvline(amounts.mean(), color=RED, linestyle="--",
               label=f"Average \u20b9{amounts.mean():,.0f}")
    ax.set_title("Size of expenses", loc="left", fontweight="bold", color=INK)
    ax.set_xlabel("Amount (\u20b9)")
    ax.set_ylabel("Number of expenses")
    ax.legend(frameon=False)
    _tidy(ax)


def _draw_box(ax, df):
    exp = _expenses(df)
    cats = sorted(exp["Category"].unique())
    data = [exp.loc[exp["Category"] == c, "Amount"] for c in cats]
    bp = ax.boxplot(data, patch_artist=True, medianprops={"color": INK})
    for patch, colour in zip(bp["boxes"], PALETTE):
        patch.set_facecolor(colour)
        patch.set_alpha(0.8)
    ax.set_xticks(range(1, len(cats) + 1))
    ax.set_xticklabels(cats, rotation=20)
    ax.set_title("Spread of spending per category", loc="left",
                 fontweight="bold", color=INK)
    ax.set_ylabel("Amount (\u20b9)")
    _tidy(ax)


def _draw_scatter(ax, df):
    for i, (cat, grp) in enumerate(_expenses(df).groupby("Category")):
        ax.scatter(grp["Day"], grp["Amount"], s=42, alpha=0.8,
                   color=PALETTE[i % len(PALETTE)], label=cat)
    ax.set_title("When do I spend? (day of month)", loc="left",
                 fontweight="bold", color=INK)
    ax.set_xlabel("Day of month")
    ax.set_ylabel("Amount (\u20b9)")
    ax.legend(frameon=False, fontsize=8, ncol=2)
    _tidy(ax)


def _draw_heatmap(ax, df):
    pv = (_expenses(df).pivot_table(index="Category", columns="Month",
                                    values="Amount", aggfunc="sum").fillna(0))
    sns.heatmap(pv, annot=True, fmt=".0f", cmap="Purples", ax=ax,
                cbar=False, linewidths=0.6, annot_kws={"fontsize": 8})
    ax.set_title("Spending heatmap", loc="left", fontweight="bold", color=INK)
    ax.set_xlabel("")
    ax.set_ylabel("")


def _draw_violin(ax, df):
    sns.violinplot(data=_expenses(df), x="Category", y="Amount", ax=ax,
                   cut=0, palette=PALETTE, hue="Category", legend=False)
    ax.set_title("Shape of spending per category", loc="left",
                 fontweight="bold", color=INK)
    ax.set_xlabel("")
    ax.set_ylabel("Amount (\u20b9)")
    ax.tick_params(axis="x", labelrotation=20)
    _tidy(ax)


def _single(draw, size=(7.5, 4.6)):
    def build(df):
        fig = Figure(figsize=size, dpi=100, layout="constrained", facecolor="white")
        draw(fig.add_subplot(111), df)
        return fig
    return build


balance_small = _single(_draw_balance, (6, 3.4))


# ================================ Plotly (opens in the browser) ==============
def plotly_monthly(df):
    g = df.groupby(["Month", "Type"], as_index=False)["Amount"].sum()
    return px.bar(g, x="Month", y="Amount", color="Type", barmode="group",
                  color_discrete_map={"Income": GREEN, "Expense": RED},
                  title="Income vs Expense by month")


def plotly_sunburst(df):
    return px.sunburst(_expenses(df), path=["Month", "Category"], values="Amount",
                       title="Spending by month and category")


def plotly_violin(df):
    return px.violin(_expenses(df), x="Category", y="Amount", color="Category",
                     box=True, title="Spending per category")


def plotly_3d(df):
    return px.scatter_3d(_expenses(df), x="Day", y="Month", z="Amount",
                         color="Category", hover_data=["Note"],
                         title="Every expense in 3D")


MATPLOTLIB_CHARTS = [
    ("Income vs Expense", _single(_draw_monthly)),
    ("Spending split", _single(_draw_donut)),
    ("Balance trend", _single(_draw_balance)),
    ("Expense sizes", _single(_draw_hist)),
    ("Category spread", _single(_draw_box)),
    ("Day vs Amount", _single(_draw_scatter)),
    ("Heatmap", _single(_draw_heatmap)),
    ("Violin", _single(_draw_violin)),
]

PLOTLY_CHARTS = [
    ("Monthly bars", plotly_monthly),
    ("Sunburst", plotly_sunburst),
    ("Violin", plotly_violin),
    ("3D view", plotly_3d),
]
