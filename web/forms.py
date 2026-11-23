from django import forms

from ledger.models import Account, DebtBalance, Goal, TaxYear


class UploadForm(forms.Form):
    file = forms.FileField()
    account = forms.ModelChoiceField(
        Account.objects.all(), required=False, empty_label="New account…"
    )
    new_account_name = forms.CharField(max_length=100, required=False)
    bank = forms.CharField(max_length=100, required=False)

    def clean(self):
        data = super().clean()
        if not data.get("account") and not data.get("new_account_name", "").strip():
            raise forms.ValidationError("Choose an account or give the new account a name.")
        name = data.get("new_account_name", "").strip()
        if not data.get("account") and Account.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError(
                f"An account named “{name}” already exists. Choose it above."
            )
        return data


class TaxYearForm(forms.ModelForm):
    class Meta:
        model = TaxYear
        fields = [f.name for f in TaxYear._meta.fields if f.name != "id"]
        widgets = {"settled_on": forms.DateInput(attrs={"type": "date"}),
                   "notes": forms.Textarea(attrs={"rows": 3})}  # fmt: skip


class DebtBalanceForm(forms.ModelForm):
    class Meta:
        model = DebtBalance
        fields = [
            "lender",
            "as_of",
            "balance",
            "annual_rate",
            "monthly_payment",
            "merchant",
            "source",
        ]
        widgets = {"as_of": forms.DateInput(attrs={"type": "date"})}


class GoalForm(forms.ModelForm):
    class Meta:
        model = Goal
        fields = ["name", "target_amount", "saved", "monthly", "target_date"]
        widgets = {"target_date": forms.DateInput(attrs={"type": "date"})}
