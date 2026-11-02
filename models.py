"""models.py - the Transaction classes used by FinTrack."""

EXPENSE_CATEGORIES = ["Food", "Transport", "Shopping", "Bills",
                      "Entertainment", "Health"]
INCOME_CATEGORIES = ["Salary", "Freelance", "Gift"]


class Transaction:
    """Base class for any money movement."""
    kind = "Transaction"

    def __init__(self, tid, date, category, amount, note=""):
        self.tid = int(tid)
        self.date = str(date)[:10]            # stored as YYYY-MM-DD
        self.category = category
        self.note = note
        self.__amount = float(amount)         # private

    @property
    def amount(self):
        return self.__amount

    def signed(self):
        """Positive for money in, negative for money out."""
        return self.amount

    def describe(self):
        return f"{self.kind}: {self.category} - {self.amount:,.2f} on {self.date}"

    def to_dict(self):
        return {"ID": self.tid, "Date": self.date, "Type": self.kind,
                "Category": self.category, "Amount": self.amount,
                "Note": self.note, "Signed": self.signed()}


class Income(Transaction):
    kind = "Income"


class Expense(Transaction):
    kind = "Expense"

    def signed(self):                          # overrides the base behaviour
        return -self.amount
