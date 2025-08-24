PY=python

.PHONY: run dev token lint unit e2e docker ci-clean demo

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8080

dev:
	ENV=dev OIDC_ISSUER= \
	$(PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

token:
	$(PY) cli/admin.py mint-token --tenant demo --subject alice --roles admin,approver --ttl 7200

lint:
	$(PY) -m pip install ruff && ruff check .

unit:
	$(PY) -m pytest -q tests/unit

e2e:
	bash tests/e2e/ci_e2e.sh

docker:
	docker compose up -d --build

ci-clean:
	docker compose down -v || true

demo:
	@echo "Starting docker stack (if needed)"; \
	docker compose up -d --build || true; \
	bash scripts/demo.sh