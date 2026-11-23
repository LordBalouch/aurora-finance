"""Synthetic bank data for demos, screenshots and the public repo. Pure Python, no Django.

One invented person with two accounts at an invented employer, shaped like a real Norwegian
household: salary with a yearly raise, rent, seasonal electricity, loans, subscriptions with a
price increase, everyday card spending, summer and Christmas travel and a few one-off costs
(car repair, dentist, Black Friday) for the anomaly detection to find. Seeded, so the same
seed and end date always give the same rows.
"""

import random
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

BILLS, CARD = "Regningskonto", "Brukskonto"


@dataclass(frozen=True)
class Row:
    account: str
    date: date
    amount: Decimal
    description: str


def _months(start: date, end: date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def _day(y: int, m: int, d: int) -> date:
    """Day d of the month, moved to the last day for short months."""
    for day in range(d, 27, -1):
        try:
            return date(y, m, day)
        except ValueError:
            continue
    return date(y, m, d)


def generate(end: date, months: int = 24, seed: int = 7) -> list[Row]:
    """Rows from the first day `months - 1` months before `end` up to `end`, sorted by date."""
    rnd = random.Random(seed)
    y, m = end.year, end.month - (months - 1)
    while m < 1:
        y, m = y - 1, m + 12
    start = date(y, m, 1)
    rows: list[Row] = []

    def add(account, day, amount, text):
        if start <= day <= end:
            rows.append(Row(account, day, Decimal(str(round(amount, 2))), text))

    for i, (y, m) in enumerate(_months(start, end)):
        second_year = i >= 12
        winter = m in (11, 12, 1, 2, 3)
        # Bills account
        salary = 38_500 * (1.035 if second_year else 1)
        add(BILLS, _day(y, m, 25), salary, "Lønn Nordlys Teknikk AS")
        rent = 14_400 if second_year else 13_900
        add(BILLS, _day(y, m, 1), -rent, "Husleie Storgata 12 Utleie AS")
        power = 520 + (1_150 if winter else 180) * rnd.uniform(0.8, 1.25)
        add(BILLS, _day(y, m, 14), -power, "Tibber Norge AS")
        add(BILLS, _day(y, m, 10), -449, "Telia Norge AS")
        add(BILLS, _day(y, m, 5), -1_120, "Gjensidige Forsikring")
        add(BILLS, _day(y, m, 15), -2_950, "Lånekassen efaktura")
        add(BILLS, _day(y, m, 20), -3_250, "Santander Consumer Bank billån")
        add(BILLS, _day(y, m, 26), -9_000, "Overføring mellom egne konti")
        add(CARD, _day(y, m, 26), 9_000, "Overføring mellom egne konti")
        add(BILLS, _day(y, m, 27), -2_000, "Nordnet spareavtale")
        if m == 3:
            add(BILLS, _day(y, m, 8), -6_840, "Fremtind Forsikring bil årspremie")
        if m == 6:
            add(BILLS, _day(y, m, 20), 4_870, "Skatteetaten skatt til gode")
        if m == 12:
            add(BILLS, _day(y, m, 31), 312.55, "Renter")

        # Card account: subscriptions
        add(CARD, _day(y, m, 3), -(149 if second_year else 129), "Visa 4821 Spotify P2c")
        add(CARD, _day(y, m, 9), -179, "Visa 4821 Netflix.com")
        add(CARD, _day(y, m, 1), -(649 if i >= 15 else 549), "Sats Norge AS")
        add(CARD, _day(y, m, 2), -899, "Vipps:Ruter Månedsbillett")

        # Everyday spending, day by day
        for d in range(1, 32):
            try:
                day = date(y, m, d)
            except ValueError:
                break
            weekend = day.weekday() >= 4
            if rnd.random() < (0.55 if weekend else 0.32):
                shop = rnd.choice(["Kiwi Torshov", "Rema 1000 Sagene", "Meny Storo", "Coop Extra"])
                size = rnd.uniform(380, 980) if day.weekday() == 5 else rnd.uniform(90, 420)
                add(CARD, day, -size, f"Visa 4821 {shop}")
            if rnd.random() < (0.30 if weekend else 0.12):
                place, lo, hi = rnd.choice([
                    ("Espresso House Storo", 55, 95),
                    ("Wolt Oslo", 230, 420),
                    ("Peppes Pizza Torggata", 320, 690),
                    ("Sushi Bar Grünerløkka", 260, 540),
                    ("Narvesen Nationaltheatret", 40, 120),
                ])  # fmt: skip
                add(CARD, day, -rnd.uniform(lo, hi), f"Visa 4821 {place}")
            if rnd.random() < 0.07:
                add(CARD, day, -rnd.uniform(450, 720), "Visa 4821 Circle K Storo")
            if rnd.random() < 0.06:
                add(CARD, day, -rnd.uniform(35, 140), "Vipps:Easypark Norge")
            if rnd.random() < 0.035:
                place, lo, hi = rnd.choice([
                    ("H&M Storo", 199, 899),
                    ("Clas Ohlson Storo", 89, 640),
                    ("Elkjøp Storo", 249, 1_990),
                    ("Apotek 1 Storo", 79, 340),
                    ("Kino Saga", 145, 290),
                    ("Vinmonopolet Storo", 189, 520),
                ])  # fmt: skip
                add(CARD, day, -rnd.uniform(lo, hi), f"Visa 4821 {place}")

        # Seasons and one-offs
        if m == 7:
            add(CARD, _day(y, m, 2), -rnd.uniform(3_200, 4_400), "Visa 4821 Norwegian Air Shuttle")
            add(CARD, _day(y, m, 12), -rnd.uniform(5_800, 7_900), "Visa 4821 Scandic Hotels")
            for d in (5, 8, 11):
                add(CARD, _day(y, m, d), -rnd.uniform(380, 820), "Visa 4821 Restaurante Mar Azul")
        if m == 12:
            add(CARD, _day(y, m, 20), -rnd.uniform(1_400, 2_100), "Visa 4821 Vy Oslo S")
            for d in (6, 13, 17):
                add(CARD, _day(y, m, d), -rnd.uniform(600, 1_800), "Visa 4821 Lekeland Storo")
        if m == 11:
            add(CARD, _day(y, m, 28), -rnd.uniform(3_900, 5_200), "Visa 4821 Elkjøp Storo")
        if i == months - 3:
            add(CARD, _day(y, m, 16), -14_380, "Visa 4821 Bilskade Senter Oslo")
        if i == 9:
            add(CARD, _day(y, m, 6), -4_250, "Visa 4821 Tannlege Torshov")
        if i % 4 == 2:
            add(CARD, _day(y, m, 18), -rnd.uniform(150, 400), "Vipps:Loppemarked Sagene")

    return sorted(rows, key=lambda r: (r.date, r.account, r.description))
