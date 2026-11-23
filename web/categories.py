"""Categories page: coverage, the inbox of uncategorized merchants, and assigning them."""

from django.db.models import Count, Max, Min, Q, Sum
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from ledger.models import Category, Rule, Transaction
from ledger.services import apply_rules

INBOX_LIMIT = 60
USER_PRIORITY = 100


def category_choices():
    parents = Category.objects.filter(parent=None).prefetch_related("children")
    return [(p.name, list(p.children.all())) for p in parents]


def _inbox(show_all: bool):
    groups = []
    for sign, cond in (("in", Q(amount__gt=0)), ("out", Q(amount__lt=0))):
        rows = (
            Transaction.objects.filter(cond, category__isnull=True)
            .exclude(merchant="")
            .values("merchant")
            .annotate(
                n=Count("id"),
                total=Sum("amount"),
                sample=Max("description_raw"),
                first=Min("date"),
                last=Max("date"),
            )
        )
        groups += [{**r, "sign": sign} for r in rows]
    groups.sort(key=lambda g: -abs(g["total"]))
    return groups if show_all else groups[:INBOX_LIMIT], len(groups)


def _coverage():
    qs = Transaction.objects.all()
    total = qs.count()
    done = qs.filter(category__isnull=False).count()
    money = qs.aggregate(
        all=Sum("amount", filter=Q(amount__lt=0)),
        done=Sum("amount", filter=Q(amount__lt=0, category__isnull=False)),
    )
    pct = round(done / total * 100) if total else 0
    money_pct = round(money["done"] / money["all"] * 100) if money["all"] else 0
    return {"total": total, "done": done, "pct": pct, "money_pct": money_pct}


def categories(request):
    inbox, groups = _inbox(request.GET.get("all") == "1")
    summary = (
        Transaction.objects.filter(category__isnull=False)
        .values("category__parent__name", "category__name", "category__kind")
        .annotate(n=Count("id"), total=Sum("amount"))
        .order_by("category__parent__name", "category__name")
    )
    return render(
        request,
        "web/categories.html",
        {
            "coverage": _coverage(),
            "inbox": inbox,
            "groups": groups,
            "choices": category_choices(),
            "summary": summary,
        },
    )


@require_POST
def assign(request):
    merchant = request.POST.get("merchant", "").strip().lower()
    sign = request.POST.get("sign")
    category = get_object_or_404(Category, pk=request.POST.get("category"), parent__isnull=False)
    if not merchant or sign not in ("in", "out"):
        return render(request, "web/_inbox_done.html", {"error": "Missing merchant."}, status=400)
    Rule.objects.update_or_create(
        pattern=merchant,
        match=Rule.Match.MERCHANT,
        sign=sign,
        defaults={"category": category, "priority": USER_PRIORITY, "source": Rule.Source.USER},
    )
    cond = Q(amount__gt=0) if sign == "in" else Q(amount__lt=0)
    result = apply_rules(Transaction.objects.filter(cond, merchant=merchant))
    return render(
        request,
        "web/_inbox_done.html",
        {
            "merchant": merchant,
            "category": category,
            "n": result["categorized"],
        },
    )
