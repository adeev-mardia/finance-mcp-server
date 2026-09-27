#!/usr/bin/env python3
"""Populate the ledger with a few months of realistic-looking demo data.

Usage:
    python scripts/seed_demo_data.py
"""

import random
from datetime import date, timedelta

from finance_mcp import db

random.seed(7)

EXPENSE_PROFILE = {
    "Groceries": (-20, -60),
    "Dining Out": (-8, -35),
    "Transport": (-3, -20),
    "Subscriptions": (-6, -16),
    "Entertainment": (-10, -45),
    "Education": (-15, -80),
    "Health": (-10, -50),
}

MERCHANTS = {
    "Groceries": ["Local Market", "Whole Foods", "Trader Joe's"],
    "Dining Out": ["Campus Cafe", "Pizza Place", "Sushi Spot"],
    "Transport": ["Uber", "Metro Card", "Gas Station"],
    "Subscriptions": ["Spotify", "Netflix", "GitHub Copilot"],
    "Entertainment": ["Cinema", "Steam", "Concert Tickets"],
    "Education": ["Udemy", "O'Reilly", "Textbook Store"],
    "Health": ["Pharmacy", "Gym", "Clinic Visit"],
}


def seed(months: int = 3) -> None:
    db.init_db()
    today = date.today()
    start = today.replace(day=1) - timedelta(days=30 * (months - 1))

    day = start
    while day <= today:
        if day.day == 1:
            db.add_transaction(2200.0, "Salary", occurred_on=day.isoformat())
            if random.random() < 0.4:
                db.add_transaction(
                    round(random.uniform(150, 500), 2), "Freelance", occurred_on=day.isoformat()
                )
            db.add_transaction(-650.0, "Rent", occurred_on=day.isoformat())

        for category, (lo, hi) in EXPENSE_PROFILE.items():
            if random.random() < 0.35:
                amount = round(random.uniform(lo, hi), 2)
                merchant = random.choice(MERCHANTS.get(category, [category]))
                db.add_transaction(amount, category, occurred_on=day.isoformat(), merchant=merchant)

        day += timedelta(days=1)

    db.set_budget("Groceries", 400.0)
    db.set_budget("Dining Out", 150.0)
    db.set_budget("Entertainment", 120.0)
    db.set_budget("Subscriptions", 40.0)

    print(f"Seeded demo data from {start} to {today} into {db.DEFAULT_DB_PATH}")


if __name__ == "__main__":
    seed()
