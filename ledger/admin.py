from django.contrib import admin

from .models import Account, ImportBatch, Transaction


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["name", "bank", "currency"]


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = [
        "file_name",
        "account",
        "importer",
        "rows_imported",
        "rows_duplicate",
        "imported_at",
    ]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["date", "amount", "description_clean", "account"]
    list_filter = ["account"]
    search_fields = ["description_clean", "description_raw"]
    date_hierarchy = "date"
