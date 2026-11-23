"""Import pages: upload → preview → confirm, and undo."""

import re

from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ledger.importers import ImportFileError
from ledger.models import Account, ImportBatch
from ledger.services import import_file, preview, undo_import

from .forms import UploadForm

UPLOADS = settings.DATA_DIR / "uploads"
_SHA = re.compile(r"^[0-9a-f]{64}$")


def _page(request, form, result=None, pending=None):
    return render(
        request,
        "web/import.html",
        {
            "form": form,
            "result": result,
            "pending": pending,
            "batches": ImportBatch.objects.select_related("account")[:20],
        },
    )


def import_page(request):
    if request.method != "POST":
        return _page(request, UploadForm())
    form = UploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return _page(request, form)
    data = form.cleaned_data["file"].read()
    account = form.cleaned_data["account"]
    try:
        result = preview(data, account)
    except ImportFileError as exc:
        form.add_error("file", str(exc))
        return _page(request, form)
    # Keep the file locally (data/ is gitignored) until the user confirms.
    UPLOADS.mkdir(parents=True, exist_ok=True)
    (UPLOADS / f"{result.sha256}.csv").write_bytes(data)
    pending = {
        "sha": result.sha256,
        "file_name": form.cleaned_data["file"].name,
        "account_id": account.pk if account else "",
        "new_account_name": form.cleaned_data["new_account_name"].strip(),
        "bank": form.cleaned_data["bank"].strip(),
        "account_label": account.name if account else form.cleaned_data["new_account_name"].strip(),
    }
    return _page(request, form, result, pending)


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
