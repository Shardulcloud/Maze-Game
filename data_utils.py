"""data_utils.py - creating, saving and analysing the transactions."""
import calendar
import os
from datetime import date, datetime

import numpy as np
import pandas as pd

from models import Income, Expense, EXPENSE_CATEGORIES

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "transactions.csv")
COLUMNS = ["ID", "Date", "Type", "Category", "Amount", "Note", "Signed"]

# Monthly budget limit for each spending category (in rupees)
BUDGETS = {"Food": 6000, "Transport": 2500, "Shopping": 6000,
           "Bills": 5000, "Entertainment": 3000, "Health": 2500}

NOTES = {"Food": ["Groceries", "Lunch", "Dinner out", "Snacks", "Coffee"],
         "Transport": ["Metro card", "Fuel", "Cab ride", "Bus pass"],
         "Shopping": ["Clothes", "Shoes", "Gadget", "Home items"],
         "Bills": ["Electricity", "Internet", "Phone recharge", "Rent share"],
         "Entertainment": ["Movie", "Games", "Streaming", "Concert"],
         "Health": ["Pharmacy", "Doctor visit", "Gym", "Checkup"]}

AMOUNT_RANGE = {"Food": (150, 900), "Transport": (60, 500),
                "Shopping": (400, 3500), "Bills": (500, 2500),
                "Entertainment": (200, 1500), "Health": (150, 1800)}

money = lambda v: f"\u20b9{v:,.0f}"


# ----------------------------------------------------------------- creating --
def generate_transactions(seed=7):
    """Make six months of realistic sample transactions."""
    rng = np.random.default_rng(seed)
    today = date.today()
    weights = np.array([0.30, 0.15, 0.15, 0.12, 0.15, 0.13])
    txns, tid = [], 1
    for back in range(5, -1, -1):
        year, month = today.year, today.month - back
        while month <= 0:
            month += 12
            year -= 1
        last_day = calendar.monthrange(year, month)[1]
        if back == 0:
            last_day = today.day

        txns.append(Income(tid, date(year, month, 1), "Salary", 52000, "Monthly salary"))
        tid += 1
        if rng.random() < 0.6:
            day = int(rng.integers(1, last_day + 1))
            txns.append(Income(tid, date(year, month, day), "Freelance",
                               int(rng.integers(3000, 12000)), "Side project"))
            tid += 1

        for _ in range(int(rng.integers(22, 30))):
            cat = str(rng.choice(EXPENSE_CATEGORIES, p=weights))
            low, high = AMOUNT_RANGE[cat]
            day = int(rng.integers(1, last_day + 1))
            txns.append(Expense(tid, date(year, month, day), cat,
                                int(rng.integers(low, high)),
                                str(rng.choice(NOTES[cat]))))
            tid += 1
    return txns


# ------------------------------------------------------------- saving/loading
def save_csv(txns, path=CSV_PATH):
    pd.DataFrame([t.to_dict() for t in txns], columns=COLUMNS).to_csv(path, index=False)


def load_csv(path=CSV_PATH):
    df = clean(pd.read_csv(path))
    kinds = {"Income": Income, "Expense": Expense}
    txns = []
    for r in df.itertuples(index=False):
        note = r.Note if isinstance(r.Note, str) else ""
        txns.append(kinds[r.Type](int(r.ID), r.Date, r.Category, r.Amount, note))
    return txns


def export_csv(df, path):
    df.drop(columns=["Month", "Day", "Signed"], errors="ignore").to_csv(path, index=False)


# ------------------------------------------------------------------ pandas ---
def clean(df):
    """Fill blank amounts (e.g. from a hand-edited CSV) with the median."""
    df = df.copy()
    df["Amount"] = df["Amount"].fillna(df.groupby("Type")["Amount"].transform("median"))
    return df


def to_dataframe(txns):
    df = pd.DataFrame([t.to_dict() for t in txns], columns=COLUMNS)
    df["Date"] = pd.to_datetime(df["Date"])
    df["Month"] = df["Date"].dt.strftime("%Y-%m")
    df["Day"] = df["Date"].dt.day
    return df.sort_values(["Date", "ID"], ascending=False).reset_index(drop=True)


def summary(df):
    income = float(df.loc[df["Type"] == "Income", "Amount"].sum())
    expense = float(df.loc[df["Type"] == "Expense", "Amount"].sum())
    balance = income - expense
    rate = balance / income * 100 if income else 0.0
    return {"income": income, "expense": expense,
            "balance": balance, "rate": float(np.round(rate, 1))}


def budget_usage(df):
    """Spending per category in the latest month: (month label, {cat: spent})."""
    if df.empty:
        return "No data", {c: 0.0 for c in BUDGETS}
    latest = df["Month"].max()
    sub = df[(df["Month"] == latest) & (df["Type"] == "Expense")]
    spent = sub.groupby("Category")["Amount"].sum()
    label = datetime.strptime(latest, "%Y-%m").strftime("%B %Y")
    return label, {c: float(spent.get(c, 0.0)) for c in BUDGETS}
