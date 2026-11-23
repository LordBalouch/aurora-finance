# Port 8010: 8000 is often taken by other local projects.
PY := .venv/bin/python

.PHONY: dev test cov lint fmt migrate import demo

dev:
	$(PY) manage.py runserver 8010

test:
	.venv/bin/pytest

# Test coverage per module (CI fails below 90 %).
cov:
	.venv/bin/pytest --cov=insights --cov=ledger --cov=ai --cov=web --cov-report=term-missing

lint:
	.venv/bin/ruff check .
	.venv/bin/ruff format --check .

fmt:
	.venv/bin/ruff check --fix .
	.venv/bin/ruff format .

migrate:
	$(PY) manage.py migrate

# Put each account's exports (CSV or XLSX) in its own folder under data/raw/. Safe to re-run.
import:
	$(PY) manage.py import_files data/raw/brukskonto/* --account Brukskonto --bank DNB
	$(PY) manage.py import_files data/raw/hovedkonto/* --account Hovedkonto --bank DNB

# Synthetic demo database (never your real data): rebuilt from scratch, served on port 8012.
DEMO := DB_PATH=data/demo.sqlite3
demo:
	rm -f data/demo.sqlite3
	$(DEMO) $(PY) manage.py migrate -v 0
	$(DEMO) $(PY) manage.py make_demo_data
	$(DEMO) $(PY) manage.py runserver 8012
