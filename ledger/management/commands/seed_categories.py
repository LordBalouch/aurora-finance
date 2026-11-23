from django.core.management.base import BaseCommand

from ledger.models import Category, Rule
from ledger.seed import CATEGORIES, RULES
from ledger.services import apply_rules


class Command(BaseCommand):
    help = "Create built-in categories and rules (idempotent; never changes your own rules)."

    def handle(self, **options):
        by_name = {}
        for (parent_name, kind), children in CATEGORIES.items():
            parent, _ = Category.objects.get_or_create(
                name=parent_name, parent=None, defaults={"kind": kind}
            )
            for child in children:
                by_name[child], _ = Category.objects.get_or_create(
                    name=child, parent=parent, defaults={"kind": kind}
                )
        created = 0
        for pattern, category, sign, match, priority in RULES:
            _, new = Rule.objects.get_or_create(
                pattern=pattern,
                match=match,
                sign=sign,
                defaults={"category": by_name[category], "priority": priority, "source": "seed"},
            )
            created += new
        result = apply_rules()
        self.stdout.write(
            self.style.SUCCESS(
                f"{len(by_name)} categories, {created} new rules. "
                f"Categorized {result['categorized']} of {result['total']} transactions."
            )
        )
