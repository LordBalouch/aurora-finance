"""Built-in categories and rules for common Norwegian merchants.

Generic only: no private person's name, and no local shop, place or station that hints at
where someone lives or travels (this file is public on GitHub). Those are your own rules.
Personal rules are made in the app and live in the local database.
"""

INC, FIX, VAR, TRF = "income", "fixed", "variable", "transfer"

CATEGORIES = {
    ("Income", INC): [
        "Salary",
        "Benefits",
        "Student loan payout",
        "Refunds & cashback",
        "Interest",
        "Other income",
    ],
    ("Practice", INC): ["Practice income"],
    ("Practice costs", FIX): ["Practice expenses"],
    ("Housing", FIX): ["Rent & mortgage", "Electricity"],
    ("Bills", FIX): ["Phone & internet", "Insurance", "Subscriptions", "Training", "Education"],
    ("Debt", FIX): ["Loans & credit", "Debt collection", "Tax"],
    ("Food", VAR): ["Groceries", "Eating out"],
    ("Transport", VAR): [
        "Fuel",
        "Parking & tolls",
        "Public transport & taxi",
        "Car",
        "EV charging",
    ],
    ("Shopping", VAR): ["Clothes", "Home & electronics", "Other shopping"],
    ("Health & care", VAR): ["Health", "Personal care"],
    ("Leisure", VAR): ["Leisure", "Travel", "Alcohol", "Gambling & lottery", "Gifts & charity"],
    ("Money", VAR): ["Cash withdrawals", "Bank fees", "Friends & family"],
    ("Transfers", TRF): ["Between own accounts", "Savings & investments"],
    ("Other", VAR): ["Miscellaneous"],
}

# (pattern, category, sign, match, priority). Defaults: sign "any", match "word", priority 50.
_W = "word"
RULES = [
    # Transfers and cash first: they must beat the shop name in 'Varekjøp Med Kib Kiwi …'.
    ("KONTOREGULERING", "Between own accounts", "any", _W, 90),
    ("MELLOM EGNE KONTI", "Between own accounts", "any", _W, 90),
    ("VERDIPAPIR", "Savings & investments", "any", _W, 80),
    ("NORDNET", "Savings & investments", "any", _W, 80),
    ("MED KIB", "Cash withdrawals", "out", _W, 80),
    ("UTTAK", "Cash withdrawals", "out", _W, 70),
    ("ATM", "Cash withdrawals", "out", _W, 70),
    ("GELDMAAT", "Cash withdrawals", "out", _W, 70),
    ("FOREX", "Cash withdrawals", "out", _W, 70),
    # Income
    ("STATENS LÅNEKASSE", "Student loan payout", "in", _W, 70),
    (r"^LØNN\b", "Salary", "in", "regex", 60),
    ("NAV", "Benefits", "in", _W, 60),
    ("HELFO", "Practice income", "in", _W, 60),
    ("TRUMF", "Refunds & cashback", "in", _W, 60),
    ("NORDIC BENEFITS", "Refunds & cashback", "in", _W, 60),
    # DNB marks card refunds with a Visa reference ending in 31.
    (r"^VISA\s+\d{4}31\b", "Refunds & cashback", "in", "regex", 60),
    (r"^RENTER\b", "Interest", "in", "regex", 60),
    # Debt, tax, bills
    ("LÅNEKASSEN", "Loans & credit", "out", _W, 60),
    ("SANTANDER", "Loans & credit", "out", _W, 50),
    ("TF BANK", "Loans & credit", "out", _W, 50),
    ("KLARNA", "Loans & credit", "out", _W, 50),
    ("NORDEA FINANS", "Loans & credit", "out", _W, 50),
    ("NORDEA FINANCE", "Loans & credit", "out", _W, 50),
    ("SVEA BANK", "Loans & credit", "out", _W, 50),
    ("SIEMENS FINANCIAL", "Loans & credit", "out", _W, 50),
    ("AMILI", "Debt collection", "out", _W, 50),
    ("RIVERTY", "Debt collection", "out", _W, 50),
    ("KREDINOR", "Debt collection", "out", _W, 50),
    ("MYNTRO", "Debt collection", "out", _W, 50),
    ("INTRUM", "Debt collection", "out", _W, 50),
    ("STATENS INNKREVINGSSENTRAL", "Debt collection", "out", _W, 55),
    ("SKATTEETATEN", "Tax", "out", _W, 50),
    ("TELIA", "Phone & internet", "out", _W, 50),
    ("PHONERO", "Phone & internet", "out", _W, 55),
    ("TELENOR", "Phone & internet", "out", _W, 50),
    ("AGVA KRAFT", "Electricity", "out", _W, 50),
    ("ELVIA", "Electricity", "out", _W, 50),
    ("TIBBER", "Electricity", "out", _W, 50),
    ("FJORDKRAFT", "Electricity", "out", _W, 50),
    ("FORSIKRING", "Insurance", "out", "contains", 45),
    ("STOREBRAND", "Insurance", "out", _W, 50),
    ("FREMTIND", "Insurance", "out", _W, 50),
    ("GJENSIDIGE", "Insurance", "out", _W, 50),
    ("SOLID FORSÄKRING", "Insurance", "out", "contains", 50),
    # Subscriptions and training
    ("APPLE.COM", "Subscriptions", "out", "contains", 50),
    ("SPOTIFY", "Subscriptions", "out", "contains", 50),
    ("NETFLIX", "Subscriptions", "out", "contains", 50),
    ("HBOMAX", "Subscriptions", "out", "contains", 50),
    ("OPENAI", "Subscriptions", "out", "contains", 50),
    ("ANTHROPIC", "Subscriptions", "out", "contains", 50),
    ("CLAUDE.AI", "Subscriptions", "out", "contains", 50),
    ("PLAYSTATION", "Subscriptions", "out", "contains", 50),
    ("NINTENDO", "Subscriptions", "out", "contains", 50),
    ("DISNEY", "Subscriptions", "out", "contains", 50),
    ("VIAPLAY", "Subscriptions", "out", "contains", 50),
    ("YOUTUBE", "Subscriptions", "out", "contains", 50),
    ("SATS", "Training", "out", _W, 50),
    ("FREE MOTION", "Training", "out", _W, 50),
    ("24FITNESS", "Training", "out", "contains", 50),
    ("EVO FITNESS", "Training", "out", _W, 50),
    ("ELIXIA", "Training", "out", _W, 50),
    # Food
    *[
        (p, "Groceries", "out", _W, 40)
        for p in (
            "KIWI",
            "MENY",
            "REMA",
            "EXTRA",
            "COOP",
            "SPAR",
            "JOKER",
            "BUNNPRIS",
            "OBS",
            "ASIA MAT",
            "STORCASH",
            "ELITE MAT",
            "ALBERT HEIJN",
            "CONAD",
            "EUROSPIN",
            "LIFE NATURKOST",
            "SUNKOST",
            "NØTTEBLANDEREN",
            "MATKROKEN",
        )
    ],
    *[
        (p, "Eating out", "out", "contains", 40)
        for p in (
            "SUSHI",
            "RESTAURANT",
            "RESTAURANG",
            "RISTORANTE",
            "TRATTORIA",
            "PIZZA",
            "KEBAB",
            "GRILL",
            "BURGER",
            "MCDONALD",
            "MC DONALD",
            "STARBUCKS",
            "ESPRESSO HOUSE",
            "JOE THE JUICE",
            "BAKER HANSEN",
            "BAKERI",
            "DOENER",
            "DÖNER",
            "GATEKJØKKEN",
            "WOLT",
            "FOODORA",
            "NARVESEN",
            "7-ELEVEN",
            "7ELEVEN",
            "COFFEE",
            "CAFE",
            "KAFE",
            "GYROS",
        )
    ],
    ("MCD", "Eating out", "out", _W, 40),
    ("BK", "Eating out", "out", _W, 40),
    ("EGON", "Eating out", "out", _W, 40),
    ("BAR", "Eating out", "out", _W, 40),
    # Transport
    *[
        (p, "Fuel", "out", _W, 40)
        for p in ("CIRCLE K", "ESSO", "ST1", "SHELL", "BP", "UNO-X", "YX")
    ],
    *[
        (p, "Parking & tolls", "out", "contains", 40)
        for p in (
            "APCOA",
            "ONEPARK",
            "AIMO PARK",
            "PARKLY",
            "EASYPARK",
            "VESTPARK",
            "TIME PARK",
            "P-NORGE",
            "PARKERING",
            "FJELLINJEN",
            "VEGFINANS",
            "AUTOPASS",
            "AUTOSYNC",
        )
    ],
    *[
        (p, "Public transport & taxi", "out", _W, 40)
        for p in (
            "VY",
            "VY APP",
            "ENTUR",
            "FLYTOGET",
            "RUTER",
            "BOLT",
            "UBER",
            "TAXI",
            "NORGESTAXI",
        )
    ],
    *[
        (p, "Car", "out", "contains", 40)
        for p in ("BILDUSJEN", "DEKK", "BILSKADE", "AUTOMOBIL", "BILTEMA", "AUTO RS")
    ],
    *[
        (p, "EV charging", "out", "contains", 45)
        for p in ("RECHARGE", "BILKRAFT", "MER NORWAY", "ELBIL")
    ],
    # Shopping
    *[
        (p, "Clothes", "out", _W, 40)
        for p in (
            "LINDEX",
            "CARLINGS",
            "H&M",
            "ZARA",
            "INDITEX",
            "CHANGE",
            "XXL",
            "SPORT OUTLET",
            "ENGEBRET SKO",
            "NEW YORKER",
            "DRESSMANN",
            "CUBUS",
            "GALANT",
            "CK STORES",
            "CARPISA",
        )
    ],
    *[
        (p, "Home & electronics", "out", _W, 40)
        for p in (
            "CLAS OHL",
            "CLAS OHLSON",
            "EUROPRIS",
            "NILLE",
            "IKEA",
            "ELKJØP",
            "ELKJOP",
            "WWW.ELKJOP.NO",
            "POWER",
            "JERNIA",
            "PLANTASJEN",
            "RUSTA",
            "JULA",
            "OBS BYGG",
            "FLUGGER",
            "FARGERIKE",
            "EPLEHUSET",
            "LAMPEHUSET",
            "MONTER",
            "NORMAL",
            "PANDURO",
            "HEMA",
            "MINISO",
        )
    ],
    *[
        (p, "Other shopping", "out", "contains", 40)
        for p in (
            "FINN.NO",
            "TOYCHAMP",
            "POP MART",
            "LEGO",
            "NORLI",
            "BARNAS HUS",
            "GLITTER",
            "MOBILE WEAR",
        )
    ],
    # Health and care
    *[
        (p, "Health", "out", "contains", 40)
        for p in (
            "APOTEK",
            "BOOTS",
            "TANNLEGE",
            "HVITE SMIL",
            "SYNOPTIK",
            "TANNHELSE",
            "MED24",
            "FARMACIA",
        )
    ],
    ("LEGE", "Health", "out", _W, 40),
    *[
        (p, "Personal care", "out", "contains", 40)
        for p in ("FRISØR", "STYLIST", "BARBER", "KICKS")
    ],
    # Leisure
    *[
        (p, "Leisure", "out", "contains", 40)
        for p in (
            "KINO",
            "TIVOLI",
            "BOWL",
        )
    ],
    *[
        (p, "Alcohol", "out", "contains", 45)
        for p in ("VINMONOPOLET", "SYSTEMBOLAGET", "GALL & GALL")
    ],
    *[
        (p, "Gambling & lottery", "out", "contains", 50)
        for p in ("NORSK TIPPING", "POSTKODELOTTERI")
    ],
    *[(p, "Gifts & charity", "out", "contains", 50) for p in ("UNICEF", "RØDE KORS", "LEGER UTEN")],
    *[
        (p, "Travel", "out", "contains", 40)
        for p in (
            "HOTEL",
            "THON",
            "SCANDIC",
            "NORWEGIAN",
            "WIDERØE",
            "TRANSAVIA",
            "DUTY-FREE",
            "AIRBNB",
            "BOOKING.COM",
            "INFLIGHT",
            "AUTOGRILL",
        )
    ],
    # Paid abroad and not matched by anything above: most likely travel.
    ("VALUTAKURS", "Travel", "out", "contains", 10),
    # Bank fees
    *[
        (p, "Bank fees", "out", "contains", 50)
        for p in ("PRISLAGTE TJENESTER", "VISA-KOSTNAD", "OMKOSTNINGER", "GEBYR")
    ],
]
