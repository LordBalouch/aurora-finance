# Phase 2 — Categorize

**Goal:** ≥90 % of transactions categorized automatically; fixing the rest is fast and teaches the system.
**Done when:** coverage % shown on dashboard, one-click recategorize creates a rule, tests for rule priority.

## Model
- `Category` (name, parent, kind: income/fixed/variable/saving/transfer, color, icon)
- `Rule` (pattern, match type: contains/regex/counterparty, amount range optional, category, priority, source: seed/user/ai, hit count)

## Tasks
- [x] 2.1 Seed categories (two levels) + ~100 seed rules for common Norwegian merchants (REMA, KIWI, Vy, Ruter, Equinor...).
- [x] 2.2 Rule engine (pure function in `insights/` or `ledger/categorize.py`): first match by priority; re-run on demand.
- [x] 2.3 Transfers between own accounts detected and excluded from spending.
- [x] 2.4 "Uncategorized" inbox: grouped by counterparty, assign category to a whole group in one click → creates a user rule.
- [ ] 2.5 Splitting one transaction across categories (optional, last).
- [x] 2.6 Tests: priority, regex safety, transfer detection.

## Note
AI suggestions for leftovers come in phase 5 (5.2), not here.

## Notes (as built)
- Seed (`ledger/seed.py`, public): generic Norwegian merchants only, never private names.
  Personal rules come from the inbox (`/categories/`) and live only in the local DB.
- Rule match types: word (default), contains, regex on the raw bank text, and merchant
  (exact `Transaction.merchant`, from `categorize.merchant_key`). Highest priority wins,
  then longest pattern. User rules = priority 100, seed 10-90.
- Transfers: DNB "Kontoregulering" / "Mellom egne konti" (prio 90). Cash inside a purchase
  ("Med Kib") beats the shop name (prio 80). Card refunds: "Visa nnnn31", money in.
- Inbox groups by merchant AND direction (money in vs out get different categories).
- Left: 2.5 split (optional); per-transaction category edit in the table; rule list/edit page;
  amount-based rules (e.g. fixed-price payments via Vipps) if the owner wants them.
