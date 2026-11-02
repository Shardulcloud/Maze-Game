"""
FinTrack - Personal Finance Manager
Made by Shardul Singh

Run with:  python main.py
"""
import os
import tkinter as tk
from datetime import date, datetime
from tkinter import ttk, messagebox, filedialog

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import charts
import data_utils as du
from models import Income, Expense, EXPENSE_CATEGORIES, INCOME_CATEGORIES

# ------------------------------------------------------------------ theme ----
FONT = "Segoe UI"
SIDEBAR, SIDE_HOVER = "#1e1b3a", "#2d2960"
ACCENT, ACCENT_HOVER = "#6c5ce7", "#5a4bd1"
BG, CARD = "#f4f6fb", "#ffffff"
INK, MUTED = "#2d3436", "#8a93a6"
GREEN, RED, AMBER = "#00b894", "#e17055", "#fdcb6e"
PILL, PILL_HOVER = "#e9ecf7", "#dadff2"


class FlatButton(tk.Label):
    """A flat button with a hover effect."""

    def __init__(self, parent, text, command, bg=ACCENT, fg="white",
                 hover=ACCENT_HOVER, size=10):
        super().__init__(parent, text=text, bg=bg, fg=fg, cursor="hand2",
                         padx=14, pady=8, font=(FONT, size, "bold"))
        self._bg, self._hover, self._command = bg, hover, command
        self.bind("<Enter>", lambda e: self.config(bg=self._hover))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg))
        self.bind("<Button-1>", lambda e: self._command())

    def restyle(self, bg, fg, hover):
        self._bg, self._hover = bg, hover
        self.config(bg=bg, fg=fg)


class NavButton(tk.Label):
    """Sidebar navigation item."""

    def __init__(self, parent, text, command):
        super().__init__(parent, text=text, anchor="w", padx=28, pady=13,
                         bg=SIDEBAR, fg="#aab0d0", font=(FONT, 11), cursor="hand2")
        self.active = False
        self.bind("<Enter>", lambda e: None if self.active else self.config(bg=SIDE_HOVER))
        self.bind("<Leave>", lambda e: None if self.active else self.config(bg=SIDEBAR))
        self.bind("<Button-1>", lambda e: command())

    def set_active(self, flag):
        self.active = flag
        self.config(bg=SIDE_HOVER if flag else SIDEBAR,
                    fg="white" if flag else "#aab0d0",
                    font=(FONT, 11, "bold" if flag else "normal"))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FinTrack  -  Personal Finance Manager")
        self.geometry("1240x770")
        self.minsize(1060, 680)
        self.configure(bg=BG)

        self._load_data()
        self._setup_style()
        self._build_menu()
        self._build_sidebar()
        self._build_content()
        self._bind_keys()

        self.current_chart = None
        self.refresh_all()
        self.show_page("Dashboard")

    # --------------------------------------------------------------- data ----
    def _load_data(self):
        try:
            self.txns = du.load_csv() if os.path.exists(du.CSV_PATH) else du.generate_transactions()
        except Exception:
            self.txns = du.generate_transactions()
        if not os.path.exists(du.CSV_PATH):
            du.save_csv(self.txns)
        self._rebuild_df()

    def _rebuild_df(self):
        self.df = du.to_dataframe(self.txns)
        self.lookup = {t.tid: t for t in self.txns}

    def _commit(self):
        """Save to disk and refresh everything after a change."""
        du.save_csv(self.txns)
        self._rebuild_df()
        self.refresh_all()

    # -------------------------------------------------------------- styling --
    def _setup_style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Fin.Treeview", background=CARD, fieldbackground=CARD,
                    foreground=INK, rowheight=34, borderwidth=0,
                    font=(FONT, 10))
        s.configure("Fin.Treeview.Heading", background="#eef0fa", foreground=INK,
                    font=(FONT, 10, "bold"), relief="flat", padding=8)
        s.map("Fin.Treeview", background=[("selected", "#dcd8fb")],
              foreground=[("selected", INK)])
        s.map("Fin.Treeview.Heading", background=[("active", "#e2e5f6")])
        s.configure("TCombobox", padding=5)

    def _build_menu(self):
        bar = tk.Menu(self)
        file_menu = tk.Menu(bar, tearoff=0)
        file_menu.add_command(label="Add transaction", accelerator="Ctrl+N",
                              command=self.add_transaction)
        file_menu.add_command(label="Export to CSV...", command=self.export_csv)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", accelerator="Ctrl+Q", command=self.destroy)
        bar.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(bar, tearoff=0)
        help_menu.add_command(label="About", command=lambda: self.show_page("About"))
        bar.add_cascade(label="Help", menu=help_menu)
        self.config(menu=bar)

    # -------------------------------------------------------------- sidebar --
    def _build_sidebar(self):
        side = tk.Frame(self, bg=SIDEBAR, width=230)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        logo = tk.Canvas(side, width=230, height=96, bg=SIDEBAR, highlightthickness=0)
        logo.pack()
        logo.create_oval(26, 28, 68, 70, fill=ACCENT, outline="")
        logo.create_text(47, 49, text="\u20b9", fill="white", font=(FONT, 17, "bold"))
        logo.create_text(82, 42, text="FinTrack", anchor="w", fill="white",
                         font=(FONT, 18, "bold"))
        logo.create_text(83, 64, text="Finance Manager", anchor="w",
                         fill="#8b8fb5", font=(FONT, 9))

        self.nav = {}
        for name, icon in [("Dashboard", "\u25a3"), ("Transactions", "\u2630"),
                           ("Analytics", "\u25a4"), ("About", "\u24d8")]:
            btn = NavButton(side, f"{icon}   {name}", lambda n=name: self.show_page(n))
            btn.pack(fill="x", pady=1)
            self.nav[name] = btn

        tk.Label(side, text="Version 1.0", bg=SIDEBAR, fg="#6f739b",
                 font=(FONT, 9)).place(relx=0.5, rely=0.97, anchor="s")

    # -------------------------------------------------------------- content --
    def _build_content(self):
        main = tk.Frame(self, bg=BG)
        main.pack(side="left", fill="both", expand=True)

        self.status = tk.StringVar()
        tk.Label(main, textvariable=self.status, anchor="w", bg=BG, fg=MUTED,
                 font=(FONT, 9), padx=28, pady=6).pack(side="bottom", fill="x")

        self.container = tk.Frame(main, bg=BG)
        self.container.pack(side="top", fill="both", expand=True)
        self.container.rowconfigure(0, weight=1)
        self.container.columnconfigure(0, weight=1)

        self.pages = {}
        for name, builder in [("Dashboard", self._build_dashboard),
                              ("Transactions", self._build_transactions),
                              ("Analytics", self._build_analytics),
                              ("About", self._build_about)]:
            page = tk.Frame(self.container, bg=BG)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[name] = page
            builder(page)

    def show_page(self, name):
        self.pages[name].tkraise()
        for n, btn in self.nav.items():
            btn.set_active(n == name)
        if name == "Analytics" and self.current_chart is None:
            label, builder = charts.MATPLOTLIB_CHARTS[0]
            self._select_chart(label, builder)

    def _heading(self, page, title, subtitle):
        tk.Label(page, text=title, bg=BG, fg=INK,
                 font=(FONT, 22, "bold")).pack(anchor="w", padx=28, pady=(24, 0))
        tk.Label(page, text=subtitle, bg=BG, fg=MUTED,
                 font=(FONT, 10)).pack(anchor="w", padx=28)

    def _embed(self, fig, parent, toolbar=False):
        for w in parent.winfo_children():
            w.destroy()
        canvas = FigureCanvasTkAgg(fig, master=parent)
        if toolbar:
            tb = NavigationToolbar2Tk(canvas, parent, pack_toolbar=False)
            tb.update()
            tb.pack(side="bottom", fill="x")
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)
        canvas.draw()

    # ------------------------------------------------------------ dashboard --
    def _stat_card(self, parent, title, var, colour):
        card = tk.Frame(parent, bg=CARD, height=98)
        card.pack_propagate(False)
        tk.Frame(card, bg=colour, width=5).place(x=0, y=0, relheight=1)
        tk.Label(card, text=title, bg=CARD, fg=MUTED,
                 font=(FONT, 10)).pack(anchor="w", padx=(24, 0), pady=(18, 0))
        tk.Label(card, textvariable=var, bg=CARD, fg=INK,
                 font=(FONT, 22, "bold")).pack(anchor="w", padx=(24, 0))
        return card

    def _build_dashboard(self, page):
        self._heading(page, "Dashboard", "Your last six months at a glance")

        row = tk.Frame(page, bg=BG)
        row.pack(fill="x", padx=22, pady=16)
        self.stat_vars = {}
        for i, (key, title, colour) in enumerate([
                ("balance", "Balance", ACCENT), ("income", "Total income", GREEN),
                ("expense", "Total expenses", RED), ("rate", "Savings rate", AMBER)]):
            row.columnconfigure(i, weight=1, uniform="stat")
            self.stat_vars[key] = tk.StringVar()
            self._stat_card(row, title, self.stat_vars[key], colour).grid(
                row=0, column=i, sticky="ew", padx=6)

        lower = tk.Frame(page, bg=BG)
        lower.pack(fill="both", expand=True, padx=22, pady=(0, 16))
        lower.rowconfigure(0, weight=1)
        lower.columnconfigure(0, weight=3, uniform="low")
        lower.columnconfigure(1, weight=2, uniform="low")

        chart_card = tk.Frame(lower, bg=CARD)
        chart_card.grid(row=0, column=0, sticky="nsew", padx=6)
        self.dash_chart = tk.Frame(chart_card, bg=CARD)
        self.dash_chart.pack(fill="both", expand=True)

        budget_card = tk.Frame(lower, bg=CARD)
        budget_card.grid(row=0, column=1, sticky="nsew", padx=6)
        tk.Label(budget_card, text="Monthly budgets", bg=CARD, fg=INK,
                 font=(FONT, 12, "bold")).pack(anchor="w", padx=16, pady=(14, 0))
        self.budget_canvas = tk.Canvas(budget_card, bg=CARD, highlightthickness=0)
        self.budget_canvas.pack(fill="both", expand=True)
        self.budget_canvas.bind("<Configure>", lambda e: self._draw_budgets())

    def _draw_budgets(self):
        c = self.budget_canvas
        c.delete("all")
        w = c.winfo_width()
        if w < 60:
            return
        month, spent = du.budget_usage(self.df)
        c.create_text(16, 16, text=month, anchor="w", fill=MUTED, font=(FONT, 10))
        y = 50
        for cat, limit in du.BUDGETS.items():
            used = spent.get(cat, 0.0)
            pct = used / limit
            colour = GREEN if pct < 0.75 else AMBER if pct < 1 else RED
            c.create_text(16, y, text=cat, anchor="w", fill=INK, font=(FONT, 10, "bold"))
            c.create_text(w - 16, y, text=f"{du.money(used)} / {du.money(limit)}",
                          anchor="e", fill=MUTED, font=(FONT, 9))
            c.create_rectangle(16, y + 14, w - 16, y + 24, fill="#eceff6", outline="")
            c.create_rectangle(16, y + 14, 16 + (w - 32) * min(pct, 1), y + 24,
                               fill=colour, outline="")
            y += 56

    # --------------------------------------------------------- transactions --
    def _build_transactions(self, page):
        top = tk.Frame(page, bg=BG)
        top.pack(fill="x")
        tk.Label(top, text="Transactions", bg=BG, fg=INK,
                 font=(FONT, 22, "bold")).pack(side="left", padx=28, pady=(24, 0))
        FlatButton(top, "+  Add transaction", self.add_transaction).pack(
            side="right", padx=28, pady=(24, 0))

        bar = tk.Frame(page, bg=BG)
        bar.pack(fill="x", padx=28, pady=12)
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(bar, textvariable=self.search_var, width=32,
                                     font=(FONT, 11), relief="flat", bg=CARD, fg=INK,
                                     insertbackground=INK, highlightthickness=1,
                                     highlightbackground="#dfe3ee", highlightcolor=ACCENT)
        self.search_entry.pack(side="left", ipady=6)
        tk.Label(bar, text="Search category or note", bg=BG, fg=MUTED,
                 font=(FONT, 9)).pack(side="left", padx=10)
        self.type_var = tk.StringVar(value="All")
        combo = ttk.Combobox(bar, textvariable=self.type_var, state="readonly",
                             values=["All", "Income", "Expense"], width=10)
        combo.pack(side="right")
        combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_table())
        self.search_entry.bind("<KeyRelease>", lambda e: self.refresh_table())

        box = tk.Frame(page, bg=CARD)
        box.pack(fill="both", expand=True, padx=28, pady=(0, 14))
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)
        cols = ["ID", "Date", "Type", "Category", "Amount", "Note"]
        self.tree = ttk.Treeview(box, columns=cols, show="headings",
                                 style="Fin.Treeview")
        widths = {"ID": 60, "Date": 120, "Type": 90, "Category": 130,
                  "Amount": 120, "Note": 260}
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths[col],
                             anchor="e" if col == "Amount" else "w")
        scroll = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.tag_configure("Income", foreground="#00a383")
        self.tree.tag_configure("Expense", foreground="#d6563a")

        self.popup = tk.Menu(self, tearoff=0)
        self.popup.add_command(label="View details", command=self.show_details)
        self.popup.add_command(label="Delete transaction", command=self.delete_transaction)
        self.tree.bind("<Button-3>", self._show_popup)
        self.tree.bind("<Button-2>", self._show_popup)
        self.tree.bind("<Double-1>", lambda e: self.show_details())
        self.tree.bind("<Delete>", lambda e: self.delete_transaction())

    def refresh_table(self):
        d = self.df
        kind = self.type_var.get()
        text = self.search_var.get().strip().lower()
        if kind != "All":
            d = d[d["Type"] == kind]
        if text:
            d = d[d["Category"].str.lower().str.contains(text, regex=False) |
                  d["Note"].str.lower().str.contains(text, regex=False)]
        self.tree.delete(*self.tree.get_children())
        for r in d.itertuples(index=False):
            sign = "+" if r.Type == "Income" else "-"
            self.tree.insert("", "end", iid=str(r.ID), tags=(r.Type,),
                             values=(r.ID, r.Date.strftime("%d %b %Y"), r.Type,
                                     r.Category, f"{sign}{du.money(r.Amount)}", r.Note))
        net = d["Signed"].sum()
        self.set_status(f"{len(d)} transactions shown  |  net {du.money(net)}  |  "
                        f"right-click a row for options")

    def _selected(self):
        sel = self.tree.selection()
        return self.lookup.get(int(sel[0])) if sel else None

    def _show_popup(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.popup.tk_popup(event.x_root, event.y_root)

    def show_details(self):
        t = self._selected()
        if t:
            messagebox.showinfo(
                f"Transaction #{t.tid}",
                f"{t.kind}\n\nCategory:  {t.category}\nAmount:    {du.money(t.amount)}\n"
                f"Date:      {t.date}\nNote:      {t.note or '-'}")

    def delete_transaction(self):
        t = self._selected()
        if t and messagebox.askyesno("Delete", f"Delete this {t.kind.lower()} "
                                               f"({t.category}, {du.money(t.amount)})?"):
            self.txns.remove(t)
            self._commit()
            self.set_status("Transaction deleted")

    def add_transaction(self):
        win = tk.Toplevel(self, bg=CARD)
        win.title("Add transaction")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        tk.Label(win, text="New transaction", bg=CARD, fg=INK,
                 font=(FONT, 15, "bold")).grid(row=0, column=0, columnspan=2,
                                               padx=24, pady=(20, 8), sticky="w")

        type_var = tk.StringVar(value="Expense")
        cat_var = tk.StringVar(value=EXPENSE_CATEGORIES[0])
        amount_var = tk.StringVar()
        date_var = tk.StringVar(value=str(date.today()))
        note_var = tk.StringVar()

        def field(row, label, widget):
            tk.Label(win, text=label, bg=CARD, fg=MUTED, font=(FONT, 10)).grid(
                row=row, column=0, padx=(24, 10), pady=7, sticky="w")
            widget.grid(row=row, column=1, padx=(0, 24), pady=7, sticky="ew")

        type_box = ttk.Combobox(win, textvariable=type_var, state="readonly",
                                values=["Expense", "Income"], width=24)
        cat_box = ttk.Combobox(win, textvariable=cat_var, state="readonly",
                               values=EXPENSE_CATEGORIES, width=24)

        def on_type(event=None):
            cats = EXPENSE_CATEGORIES if type_var.get() == "Expense" else INCOME_CATEGORIES
            cat_box.config(values=cats)
            cat_var.set(cats[0])
        type_box.bind("<<ComboboxSelected>>", on_type)

        field(1, "Type", type_box)
        field(2, "Category", cat_box)
        field(3, "Amount (\u20b9)", ttk.Entry(win, textvariable=amount_var, width=27))
        field(4, "Date (YYYY-MM-DD)", ttk.Entry(win, textvariable=date_var, width=27))
        field(5, "Note", ttk.Entry(win, textvariable=note_var, width=27))

        def save():
            try:
                amount = float(amount_var.get().replace(",", ""))
                if amount <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid amount", "Amount must be a positive number.",
                                     parent=win)
                return
            try:
                when = datetime.strptime(date_var.get().strip(), "%Y-%m-%d").date()
            except ValueError:
                messagebox.showerror("Invalid date", "Use the format 2026-10-28.",
                                     parent=win)
                return
            kind = Income if type_var.get() == "Income" else Expense
            new_id = max(self.lookup, default=0) + 1
            self.txns.append(kind(new_id, when, cat_var.get(), amount,
                                  note_var.get().strip()))
            self._commit()
            win.destroy()
            self.set_status(f"Added {cat_var.get()} {du.money(amount)}")

        row = tk.Frame(win, bg=CARD)
        row.grid(row=6, column=0, columnspan=2, pady=(10, 22))
        FlatButton(row, "Save", save).pack(side="left", padx=6)
        FlatButton(row, "Cancel", win.destroy, bg=PILL, fg=INK,
                   hover=PILL_HOVER).pack(side="left", padx=6)
        win.bind("<Return>", lambda e: save())

    # ------------------------------------------------------------ analytics --
    def _build_analytics(self, page):
        self._heading(page, "Analytics", "Pick a chart to explore your money")

        pills = tk.Frame(page, bg=BG)
        pills.pack(fill="x", padx=22, pady=(12, 0))
        self.pill_buttons = {}
        for i, (label, builder) in enumerate(charts.MATPLOTLIB_CHARTS):
            pills.columnconfigure(i % 4, weight=1, uniform="pill")
            b = FlatButton(pills, label, lambda l=label, b_=builder: self._select_chart(l, b_),
                           bg=PILL, fg=INK, hover=PILL_HOVER)
            b.grid(row=i // 4, column=i % 4, sticky="ew", padx=6, pady=4)
            self.pill_buttons[label] = b

        tk.Label(page, text="Interactive views  (open in your browser)", bg=BG,
                 fg=MUTED, font=(FONT, 9)).pack(anchor="w", padx=28, pady=(8, 0))
        web = tk.Frame(page, bg=BG)
        web.pack(fill="x", padx=22)
        for i, (label, builder) in enumerate(charts.PLOTLY_CHARTS):
            web.columnconfigure(i, weight=1, uniform="web")
            FlatButton(web, label, lambda b_=builder: self.open_plotly(b_),
                       bg="#ece9fd", fg=ACCENT, hover="#dcd8fb").grid(
                row=0, column=i, sticky="ew", padx=6, pady=4)

        self.chart_card = tk.Frame(page, bg=CARD)
        self.chart_card.pack(fill="both", expand=True, padx=28, pady=(8, 14))

    def _select_chart(self, label, builder):
        self.current_chart = (label, builder)
        for name, btn in self.pill_buttons.items():
            if name == label:
                btn.restyle(ACCENT, "white", ACCENT_HOVER)
            else:
                btn.restyle(PILL, INK, PILL_HOVER)
        self._render_chart()

    def _render_chart(self):
        if not self.current_chart:
            return
        label, builder = self.current_chart
        try:
            fig = builder(self.df)
        except Exception as err:
            messagebox.showerror("Chart error", str(err))
            return
        self._embed(fig, self.chart_card, toolbar=True)
        self.set_status(f"{label}  |  use the toolbar below the chart to zoom or save")

    def open_plotly(self, builder):
        try:
            builder(self.df).show()
            self.set_status("Opened in your web browser")
        except Exception as err:
            messagebox.showerror("Chart error", str(err))

    # ---------------------------------------------------------------- about --
    def _build_about(self, page):
        card = tk.Frame(page, bg=CARD)
        card.place(relx=0.5, rely=0.46, anchor="center", width=520, height=400)

        logo = tk.Canvas(card, width=96, height=96, bg=CARD, highlightthickness=0)
        logo.pack(pady=(34, 6))
        logo.create_oval(8, 8, 88, 88, fill=ACCENT, outline="")
        logo.create_text(48, 48, text="\u20b9", fill="white", font=(FONT, 34, "bold"))

        tk.Label(card, text="FinTrack", bg=CARD, fg=INK,
                 font=(FONT, 26, "bold")).pack()
        tk.Label(card, text="Personal Finance Manager", bg=CARD, fg=MUTED,
                 font=(FONT, 11)).pack(pady=(0, 14))
        tk.Frame(card, bg="#e7eaf4", height=1).pack(fill="x", padx=60)
        tk.Label(card, text="MADE BY", bg=CARD, fg=MUTED,
                 font=(FONT, 9, "bold")).pack(pady=(18, 0))
        tk.Label(card, text="Shardul Singh", bg=CARD, fg=ACCENT,
                 font=(FONT, 24, "bold")).pack()
        tk.Label(card, text="Track your income and spending, keep an eye on\n"
                            "your budgets, and see where your money goes.",
                 bg=CARD, fg=MUTED, font=(FONT, 10), justify="center").pack(pady=(14, 0))
        tk.Label(card, text="Version 1.0", bg=CARD, fg="#b2b9c9",
                 font=(FONT, 9)).pack(side="bottom", pady=16)

    # ---------------------------------------------------------------- misc ---
    def refresh_all(self):
        s = du.summary(self.df)
        self.stat_vars["balance"].set(du.money(s["balance"]))
        self.stat_vars["income"].set(du.money(s["income"]))
        self.stat_vars["expense"].set(du.money(s["expense"]))
        self.stat_vars["rate"].set(f"{s['rate']:.0f}%")
        try:
            self._embed(charts.balance_small(self.df), self.dash_chart)
        except Exception:
            pass
        self._draw_budgets()
        self.refresh_table()
        self._render_chart()

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            filetypes=[("CSV file", "*.csv")],
                                            initialfile="my_transactions.csv")
        if path:
            du.export_csv(self.df, path)
            self.set_status(f"Saved to {path}")

    def _bind_keys(self):
        self.bind("<Control-n>", lambda e: self.add_transaction())
        self.bind("<Control-q>", lambda e: self.destroy())
        self.bind("<Control-f>", lambda e: (self.show_page("Transactions"),
                                            self.search_entry.focus()))
        for i, name in enumerate(["Dashboard", "Transactions", "Analytics", "About"], 1):
            self.bind(f"<Control-Key-{i}>", lambda e, n=name: self.show_page(n))

    def set_status(self, text):
        self.status.set(text)


if __name__ == "__main__":
    App().mainloop()
