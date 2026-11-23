from datetime import date

from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import render

from ledger.models import Account, Transaction

from .categories import category_choices

PAGE_SIZE = 50


def _date(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def transactions(request):
    qs = Transaction.objects.select_related("account", "category")
    q = request.GET.get("q", "").strip()
    account = request.GET.get("account", "")
    category = request.GET.get("category", "")
    start, end = _date(request.GET.get("from")), _date(request.GET.get("to"))
    if q:
        qs = qs.filter(Q(description_clean__icontains=q) | Q(description_raw__icontains=q))
    merchant = request.GET.get("merchant", "").strip()
    if merchant:
        qs = qs.filter(merchant=merchant)
    if account.isdigit():
        qs = qs.filter(account_id=int(account))
    if category == "none":
        qs = qs.filter(category__isnull=True)
    elif category.isdigit():
        qs = qs.filter(Q(category_id=int(category)) | Q(category__parent_id=int(category)))
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lte=end)

    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    context = {
        "page": page,
        "query": params.urlencode(),
        "q": q,
        "account": account,
        "start": start,
        "end": end,
        "accounts": Account.objects.all(),
        "category": category,
        "choices": category_choices(),
        "totals": qs.aggregate(
            n=Count("id"),
            money_in=Sum("amount", filter=Q(amount__gt=0)),
            money_out=Sum("amount", filter=Q(amount__lt=0)),
        ),
    }
    if request.headers.get("HX-Request") and request.GET.get("page"):
        return render(request, "web/_transaction_rows.html", context)
    if request.headers.get("HX-Request"):
        return render(request, "web/_transaction_results.html", context)
    return render(request, "web/transactions.html", context)
