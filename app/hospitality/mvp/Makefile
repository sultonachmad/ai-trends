.PHONY: install dev stop backend frontend migrate

install:
	cd backend && python3 -m venv .venv && if [ -f constraints.txt ]; then c="$$PWD/constraints.txt"; if (LC_ALL=C; case "$$c" in *[!!-~]*) exit 0;; esac; exit 1); then echo "WARNING: the path to backend/constraints.txt contains whitespace or a character outside printable ASCII, so pip gets the relative path constraints.txt" >&2; c=constraints.txt; fi; export PIP_CONSTRAINT="$$c" PIP_BUILD_CONSTRAINT="$$c"; fi && .venv/bin/pip install -e "."
	cd frontend && npm install

dev:
	bash scripts/dev.sh

backend:
	cd backend && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

frontend:
	cd frontend && npm run dev

migrate:
	cd backend && source .venv/bin/activate && alembic upgrade head

migrate-new:
	cd backend && source .venv/bin/activate && alembic revision --autogenerate -m "$(name)"
