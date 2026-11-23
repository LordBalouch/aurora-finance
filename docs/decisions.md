# Key decisions

Short and in no particular order. Each one says what was chosen, and why.

- **Local only, one user, no login.** The data is a person's bank history. The safest
  server is no server at all. It could move online later, but that is not planned.
- **SQLite and Django.** One file, nothing to install, and backups are a file copy. Django
  provides models, migrations, forms and an admin, so the time goes into the analysis.
- **Analysis in pure pandas (`insights/`), not in the views.** Every function is
  DataFrame in, DataFrame out. They are tested without a database and can be reused from a
  notebook.
- **Money is `Decimal` in the database, float only inside pandas.** Stored amounts are
  exact, while analysis can be fast. Results are rounded before they are shown.
- **Rules before AI for categorization.** Rules are explainable, free and deterministic.
  About 250 built-in patterns, plus your own, cover nearly every transaction, and an inbox
  shows the rest.
- **Fingerprint deduplication.** Each row is identified by its date, amount, cleaned text
  and how many identical rows came before it that day. Overlapping exports can be imported
  again safely, and two genuinely identical purchases on the same day are both kept.
- **Transfers and money between friends are not spending.** Otherwise moving money between
  your own accounts would double count, and splitting a dinner bill would look like
  income.
- **Robust statistics (median and MAD) for anomalies.** Personal spending is spiky, and a
  mean and standard deviation would let a single holiday hide everything else.
- **HTMX and hand-written CSS, no JavaScript build.** There is little code to maintain,
  pages render on the server, and the design tokens keep every chart and page consistent.
- **The AI sees only computed numbers, never raw transactions.** Each card sends a small
  fact sheet that the server built. The model must answer in a fixed JSON schema, and
  answers are cached by the exact prompt. Every number in a tip can be traced to the data.
- **Demo data goes through the real pipeline.** The generator writes bank-style text, and
  the real rules categorize it. The demo therefore shows how the categorizer actually
  behaves, and screenshots never need real data.
