"""Import pages: upload → preview → confirm, and undo. A file with columns we do not know
gets one extra step: the user picks the columns, and that choice is remembered."""

import hashlib
import re

from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ledger.importers import FIELDS, ImportFileError, UnknownColumns, read_table
from ledger.importers.generic import _find
from ledger.models import Account, BankFormat, ImportBatch
from ledger.services import import_file, preview, teach_format, undo_import

from .forms import UploadForm

UPLOADS = settings.DATA_DIR / "uploads"
_SHA = re.compile(r"^[0-9a-f]{64}$")


FIELD_LABELS = {
    "date": "Date",
    "description": "Text (what the payment was)",
    "amount": "Amount (money out negative)",
    "in": "Money in (if separate)",
    "out": "Money out (if separate)",
    "balance": "Balance (optional)",
}


def _page(request, form, result=None, pending=None, mapping=None):
    return render(
        request,
        "web/import.html",
        {
            "form": form,
            "result": result,
            "pending": pending,
            "mapping": mapping,
            "batches": ImportBatch.objects.select_related("account")[:20],
            "formats": BankFormat.objects.all(),
        },
    )


def _pending(form_data: dict, sha: str, file_name: str) -> dict:
    account = form_data.get("account")
    new_name = (form_data.get("new_account_name") or "").strip()
    return {
        "sha": sha,
        "file_name": file_name,
        "account_id": account.pk if account else "",
        "new_account_name": new_name,
        "bank": (form_data.get("bank") or "").strip(),
        "account_label": account.name if account else new_name,
    }


def _mapping(data: bytes, header: list[str], chosen: dict | None = None, name: str = "") -> dict:
    """What the column-choice step needs: the header, a few rows and a first guess."""
    _, rows = read_table(data)
    guess = chosen if chosen is not None else _find(header)
    return {
        "header": [h for h in header if h],
        "rows": [[r.get(h, "") for h in header if h] for r in rows[:5]],
        "fields": [(f, FIELD_LABELS[f], guess.get(f, "")) for f in FIELDS],
        "name": name,
    }


def import_page(request):
    if request.method != "POST":
        return _page(request, UploadForm())
    form = UploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return _page(request, form)
    data = form.cleaned_data["file"].read()
    account = form.cleaned_data["account"]
    sha = hashlib.sha256(data).hexdigest()
    pending = _pending(form.cleaned_data, sha, form.cleaned_data["file"].name)
    try:
        result = preview(data, account)
    except UnknownColumns as exc:
        # Keep the file locally (data/ is gitignored) while the user picks the columns.
        _store(sha, data)
        mapping = _mapping(data, exc.header, name=pending["bank"])
        return _page(request, form, pending=pending, mapping=mapping)
    except ImportFileError as exc:
        form.add_error("file", str(exc))
        return _page(request, form)
    # Keep the file locally (data/ is gitignored) until the user confirms.
    _store(sha, data)
    return _page(request, form, result, pending)


def _store(sha: str, data: bytes) -> None:
    UPLOADS.mkdir(parents=True, exist_ok=True)
    (UPLOADS / f"{sha}.csv").write_bytes(data)


@require_POST
def import_map(request):
    """The column-choice step: remember the columns for this layout, then show the preview."""
    sha = request.POST.get("sha", "")
    path = UPLOADS / f"{sha}.csv"
    if not _SHA.match(sha) or not path.exists():
        messages.error(request, "The uploaded file is gone. Please upload it again.")
        return redirect("web:import")
    data = path.read_bytes()
    account = None
    if request.POST.get("account_id"):
        account = get_object_or_404(Account, pk=request.POST["account_id"])
    pending = _pending(
        {
            "account": account,
            "new_account_name": request.POST.get("new_account_name", ""),
            "bank": request.POST.get("bank", ""),
        },
        sha,
        request.POST.get("file_name", "upload.csv"),
    )
    chosen = {f: request.POST.get(f"col_{f}", "") for f in FIELDS}
    name = request.POST.get("format_name", "").strip() or pending["bank"] or "My bank"
    try:
        teach_format(data, name, chosen)
        result = preview(data, account)
    except ImportFileError as exc:
        header, _ = read_table(data)
        mapping = {**_mapping(data, header, chosen, name), "error": str(exc)}
        return _page(request, UploadForm(), pending=pending, mapping=mapping)
    messages.success(
        request, f"Saved the columns as “{name}”. Files like this now import directly."
    )
    return _page(request, UploadForm(), result, pending)


@require_POST
def format_delete(request, pk):
    fmt = get_object_or_404(BankFormat, pk=pk)
    fmt.delete()
    messages.success(request, f"Forgot the column choice “{fmt.name}”.")
    return redirect("web:import")


@require_POST
def import_confirm(request):
    sha = request.POST.get("sha", "")
    path = UPLOADS / f"{sha}.csv"
    if not _SHA.match(sha) or not path.exists():
        messages.error(request, "The uploaded file is gone. Please upload it again.")
        return redirect("web:import")
    if request.POST.get("account_id"):
        account = get_object_or_404(Account, pk=request.POST["account_id"])
    else:
        account, _ = Account.objects.get_or_create(
            name=request.POST.get("new_account_name", "").strip() or "Main account",
            defaults={"bank": request.POST.get("bank", "").strip()},
        )
    batch = import_file(path.read_bytes(), request.POST.get("file_name", "upload.csv"), account)
    path.unlink(missing_ok=True)
    messages.success(
        request,
        f"Imported {batch.rows_imported} transactions into {account.name}"
        + (f" ({batch.rows_duplicate} already there, skipped)." if batch.rows_duplicate else "."),
    )
    return redirect(f"{reverse('web:transactions')}?account={account.pk}")


@require_POST
def import_undo(request, pk):
    batch = get_object_or_404(ImportBatch, pk=pk)
    removed = undo_import(batch)
    messages.success(request, f"Undid “{batch.file_name}”: {removed} transactions removed.")
    return redirect("web:import")
