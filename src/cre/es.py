"""Connexion à Elasticsearch et création des index / pipelines du lab."""

from __future__ import annotations

import json
import os
from pathlib import Path

from elasticsearch import Elasticsearch

ROOT = Path(__file__).resolve().parents[2]
ELASTIC_DIR = ROOT / "elastic"

INDEX_DEFAULT = "cre-default"
INDEX_TUNED = "cre-tuned"
INDEX_HORS_PROD = "cre-hors-prod"


def client() -> Elasticsearch:
    return Elasticsearch(os.environ.get("ES_URL", "http://localhost:9200"), request_timeout=600)


def _load(name: str) -> dict:
    return json.loads((ELASTIC_DIR / name).read_text(encoding="utf-8"))


def anonymize_pipeline() -> dict:
    salt = os.environ.get("CRE_ANON_SALT", "lab-salt-a-changer")
    raw = (ELASTIC_DIR / "pipeline-anonymize.json").read_text(encoding="utf-8")
    return json.loads(raw.replace("CHANGE-ME-SALT", salt))


def setup(es: Elasticsearch, reset: bool = False) -> None:
    """Crée les pipelines d'ingestion et les deux index à comparer."""
    es.ingest.put_pipeline(id="cre-realtime", body=_load("pipeline-realtime.json"))
    es.ingest.put_pipeline(id="cre-anonymize", body=anonymize_pipeline())

    for index, file in ((INDEX_DEFAULT, "cre-default.json"), (INDEX_TUNED, "cre-tuned.json")):
        if es.indices.exists(index=index):
            if not reset:
                continue
            es.indices.delete(index=index)
        es.indices.create(index=index, body=_load(file))


def create_hors_prod_index(es: Elasticsearch) -> None:
    """Index cible hors production : même mapping optimisé, sans pipeline temps réel."""
    if es.indices.exists(index=INDEX_HORS_PROD):
        es.indices.delete(index=INDEX_HORS_PROD)
    body = _load("cre-tuned.json")
    body["settings"].pop("index.default_pipeline")
    body["mappings"]["properties"]["anonymized"] = {"type": "boolean"}
    es.indices.create(index=INDEX_HORS_PROD, body=body)
