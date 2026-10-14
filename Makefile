PY := .venv/bin/python

.PHONY: install up down setup stream bench anonymize lucene kibana demo test

install:
	python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]"

up:
	docker compose up -d

down:
	docker compose down

setup:
	$(PY) -m cre setup --reset

stream:
	$(PY) -m cre stream --rate 500 --duration 60

bench:
	$(PY) -m cre bench --docs 1000000

anonymize:
	$(PY) -m cre anonymize --pct 10 | tee results/anonymize.json

lucene:
	$(PY) -m cre lucene --index cre-tuned

kibana:
	$(PY) -m cre kibana

demo:
	$(PY) -m cre stream --rate 200 --duration 3600

test:
	.venv/bin/pytest -q
