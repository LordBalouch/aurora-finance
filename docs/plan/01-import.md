# Phase 1 — Import

**Goal:** bank exports in, clean transactions out, safe to import twice.
**Done when:** a real export imports via the UI with a preview, re-import adds 0 rows, tests cover each bank format.

## Data model (ledger app)
- `Account` (name, bank, type, currency)
- `Transaction` (account, date, amount Decimal, description_raw, description_clean, balance, fingerprint unique per account, import_batch FK). Category FK comes in phase 2; counterparty extraction too.
- `ImportBatch` (file name, file hash, bank, row counts, imported_at) — lets the user undo one import.

## Tasks
- [x] 1.1 Models + migrations + admin.
- [x] 1.2 Importer interface + `GenericImporter` (columns by name; signed amount or in/out). Verified on the owner's real DNB exports, CSV and XLSX (identical fingerprints across formats). No bank-specific importer needed.
- [x] 1.3 Normalization: Norwegian number format (`1 234,56`), date formats, encoding (UTF-8 / Windows-1252), clean description (strip card numbers, "VISA VAREKJØP" noise).
- [x] 1.4 Dedup: fingerprint = hash(account, date, amount, clean description, occurrence index within that day).
- [x] 1.5 Upload page: drag-and-drop, preview table (first 20 rows, totals, duplicates found), confirm → import.
- [x] 1.6 Transactions page: searchable, filterable table (HTMX), infinite scroll.
- [x] 1.7 Undo an import batch.
- [x] 1.8 Tests with small fake CSV fixtures per bank (never real files).

## Notes (as built)
- Pipeline: `importers.read_table` (encoding + delimiter sniff) → `detect(header)` → `parse` → `dedup.fingerprints` → `services.preview/import_file`.
- Zero-amount rows (reservations, info lines) are skipped.
- Preview stores the upload in `data/uploads/<sha>.csv` until confirm; confirm validates the sha.
- Fingerprint = date + amount + cleaned text + occurrence that day. If a bank changes the text of
  a transaction between exports (pending → booked), it will look new — watch for this with real files.
- DNB file names (`Kontoutskrift (n)`) do not say which account. Keep one folder per account in
  `data/raw/<account>/` and run `make import`. A file put in the wrong account can be undone.
- DNB "historikk.csv" (payment history) is NOT imported: it duplicates the statements with other text.
