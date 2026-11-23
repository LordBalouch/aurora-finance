from django.db import models


class Account(models.Model):
    name = models.CharField(max_length=100, unique=True)
    bank = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=40, blank=True)
    currency = models.CharField(max_length=3, default="NOK")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ImportBatch(models.Model):
    """One imported file. Deleting a batch undoes the import (its transactions cascade)."""

    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="imports")
    file_name = models.CharField(max_length=255)
    file_sha256 = models.CharField(max_length=64)
    importer = models.CharField(max_length=50)
    rows_total = models.PositiveIntegerField()
    rows_imported = models.PositiveIntegerField()
    rows_duplicate = models.PositiveIntegerField()
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-imported_at"]

    def __str__(self):
        return f"{self.file_name} → {self.account}"


class Category(models.Model):
    class Kind(models.TextChoices):
        INCOME = "income", "Income"
        FIXED = "fixed", "Fixed cost"
        VARIABLE = "variable", "Variable cost"
        TRANSFER = "transfer", "Transfer"

    name = models.CharField(max_length=80)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)

    class Meta:
        ordering = ["parent__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["parent", "name"], name="uniq_category_name"),
        ]
        verbose_name_plural = "categories"

    def __str__(self):
        return f"{self.parent.name} › {self.name}" if self.parent_id else self.name


class Rule(models.Model):
    """Maps transactions to a category. Highest priority wins; ties go to the longest pattern."""

    class Match(models.TextChoices):
        WORD = "word", "Whole words in the bank text"
        CONTAINS = "contains", "Anywhere in the bank text"
        REGEX = "regex", "Regular expression on the bank text"
        MERCHANT = "merchant", "Exact merchant"

    class Sign(models.TextChoices):
        ANY = "any", "In and out"
        IN = "in", "Money in"
        OUT = "out", "Money out"

    class Source(models.TextChoices):
        SEED = "seed", "Built-in"
        USER = "user", "You"
        AI = "ai", "AI suggestion"

    pattern = models.CharField(max_length=200)
    match = models.CharField(max_length=10, choices=Match.choices, default=Match.WORD)
    sign = models.CharField(max_length=3, choices=Sign.choices, default=Sign.ANY)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="rules")
    priority = models.IntegerField(default=50)
    source = models.CharField(max_length=4, choices=Source.choices, default=Source.USER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-priority", "pattern"]
        constraints = [
            models.UniqueConstraint(fields=["pattern", "match", "sign"], name="uniq_rule"),
        ]

    def __str__(self):
        return f"{self.pattern} → {self.category}"


class Transaction(models.Model):
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="transactions")
    import_batch = models.ForeignKey(
        ImportBatch, on_delete=models.CASCADE, related_name="transactions"
    )
    date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description_raw = models.CharField(max_length=500)
    description_clean = models.CharField(max_length=500, db_index=True)
    balance = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    merchant = models.CharField(max_length=120, blank=True, db_index=True)
    category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="transactions"
    )
    rule = models.ForeignKey(Rule, null=True, blank=True, on_delete=models.SET_NULL)
    # Set by hand: rules never overwrite it.
    category_locked = models.BooleanField(default=False)
    # Stable identity of a bank transaction, so re-importing overlapping files adds nothing.
    fingerprint = models.CharField(max_length=64)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["account", "fingerprint"], name="uniq_txn_per_account"),
        ]

    def __str__(self):
        return f"{self.date} {self.amount} {self.description_clean}"


def _money(help_text: str = ""):
    return models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                               help_text=help_text)  # fmt: skip


class TaxYear(models.Model):
    """Key figures from one year's tax settlement (Skatteoppgjør, Skatteetaten), entered by hand.
    help_text names the line in the Norwegian settlement. All amounts in NOK; blank = not given."""

    year = models.PositiveIntegerField(unique=True)
    settled_on = models.DateField(null=True, blank=True, help_text="Ordinær fastsetting")
    # Income
    business_profit = _money("Overskudd fra annen næring")
    wages = _money("Lønn og trekkpliktige ytelser")
    benefits = _money("Pensjon, trygd og stønader")
    interest_income = _money("Renter av bankinnskudd (incl. children's accounts)")
    other_income = _money("Other income lines")
    total_income = _money("Sum inntekter")
    personal_income = _money("Personinntekt / pensjonsgivende inntekt")
    # Deductions
    interest_expense = _money("Renter på lån")
    other_deductions = _money("Other deductions (barnepass, gaver, fagforening …)")
    total_deductions = _money("Sum fradrag")
    general_income = _money("Alminnelig inntekt før særfradrag")
    # Tax
    tax_assessed = _money("Beregnet skatt og avgift")
    tax_prepaid = _money("Utskrevet forskuddsskatt / forskuddstrekk")
    settlement = _money("Til gode (+) or restskatt (−), incl. interest on it")
    # Wealth (values as assessed, before valuation discounts) and debt, at 31 December
    bank_deposits = _money("Bankinnskudd (incl. children's accounts)")
    funds_and_shares = _money("Verdipapirfond, aksjesparekonto")
    vehicles = _money("Kjøretøy")
    business_assets = _money("Driftsmidler og annen formue fra næringsvirksomhet")
    other_assets = _money("Other assets (bolig, fritidsbolig …)")
    gross_wealth = _money("Bruttoformue")
    debt = _money("Sum gjeld")
    net_wealth = _money("Nettoformue")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["year"]

    def __str__(self):
        return f"Tax year {self.year}"


class DebtBalance(models.Model):
    """What one loan or credit stood at on a date (tax settlement, Gjeldsregisteret, statement)."""

    class Source(models.TextChoices):
        TAX = "tax", "Tax settlement"
        REGISTER = "register", "Gjeldsregisteret"
        STATEMENT = "statement", "Lender statement"
        MANUAL = "manual", "Entered by hand"

    lender = models.CharField(max_length=120)
    as_of = models.DateField()
    balance = models.DecimalField(max_digits=14, decimal_places=2)
    annual_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, help_text="Nominal rate, % per year"
    )
    monthly_payment = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Leave blank to use what the bank data shows for the merchant below",
    )  # fmt: skip
    merchant = models.CharField(
        max_length=120, blank=True, help_text="Merchant key of the payments in the bank data"
    )
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)

    class Meta:
        ordering = ["lender", "-as_of"]
        constraints = [
            models.UniqueConstraint(fields=["lender", "as_of"], name="uniq_debt_balance"),
        ]

    def __str__(self):
        return f"{self.lender} {self.as_of}: {self.balance}"


class Budget(models.Model):
    """Planned spending for one category group in one month."""

    month = models.DateField(help_text="First day of the month")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="budgets")
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["month", "category__name"]
        constraints = [
            models.UniqueConstraint(fields=["month", "category"], name="uniq_budget"),
        ]

    def __str__(self):
        return f"{self.month:%Y-%m} {self.category}: {self.amount}"


class Goal(models.Model):
    """A savings goal. Progress is entered by hand: savings sit in an account not imported."""

    name = models.CharField(max_length=120)
    target_amount = models.DecimalField(max_digits=14, decimal_places=2)
    saved = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    monthly = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, help_text="Planned saving per month"
    )
    target_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["target_date", "name"]

    def __str__(self):
        return self.name


class AIAdvice(models.Model):
    """One answer from the AI, cached by the exact request so the same question costs once."""

    key = models.CharField(max_length=64, unique=True, help_text="sha256 of model + prompt")
    card = models.CharField(max_length=40)
    model = models.CharField(max_length=60)
    facts = models.TextField(help_text="What the AI saw (JSON)")
    answer = models.JSONField()
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.card} {self.created_at:%Y-%m-%d %H:%M}"
