"""Jeu de données hors production : réduction par échantillon de comptes + pseudonymisation.

On échantillonne par compte et non par événement : un compte retenu garde tout
son historique, ce qui laisse des scénarios de test cohérents (soldes, séquences
d'opérations). Le filtre s'appuie sur les Doc Values du champ account_id.
"""

from __future__ import annotations

from elasticsearch import Elasticsearch

from .es import INDEX_HORS_PROD, INDEX_TUNED, create_hors_prod_index

SAMPLE_QUERY = {
    "script": {
        "script": {
            "lang": "painless",
            "source": "int h = doc['account_id'].value.hashCode() % 100; return (h < 0 ? h + 100 : h) < params.pct;",
            "params": {},
        }
    }
}


def run(es: Elasticsearch, pct: int) -> dict:
    create_hors_prod_index(es)
    query = {"bool": {"filter": [SAMPLE_QUERY]}}
    query["bool"]["filter"][0]["script"]["script"]["params"]["pct"] = pct

    result = es.reindex(
        source={"index": INDEX_TUNED, "query": query},
        dest={"index": INDEX_HORS_PROD, "pipeline": "cre-anonymize"},
        wait_for_completion=True, refresh=True,
    )

    def accounts(index: str) -> int:
        aggs = es.search(index=index, size=0, aggs={"n": {"cardinality": {"field": "account_id"}}})
        return aggs["aggregations"]["n"]["value"]

    # Contrôle de fuite : aucun IBAN réel ne doit se retrouver hors production.
    sample = es.search(index=INDEX_TUNED, size=200, source=["iban"])["hits"]["hits"]
    real_ibans = list({h["_source"]["iban"] for h in sample})
    leaks = es.count(index=INDEX_HORS_PROD, query={"terms": {"iban": real_ibans}})["count"]

    before = es.search(index=INDEX_TUNED, size=1, query=query, sort=[{"@timestamp": "desc"}])["hits"]["hits"][0]["_source"]
    after = es.search(index=INDEX_HORS_PROD, size=1, sort=[{"@timestamp": "desc"}])["hits"]["hits"][0]["_source"]

    return {
        "source_docs": es.count(index=INDEX_TUNED)["count"],
        "hors_prod_docs": result["created"],
        "source_accounts": accounts(INDEX_TUNED),
        "hors_prod_accounts": accounts(INDEX_HORS_PROD),
        "ibans_reels_retrouves": leaks,
        "exemple_avant": {k: before[k] for k in ("account_id", "iban", "holder_name", "label", "amount")},
        "exemple_apres": {k: after[k] for k in ("account_id", "iban", "holder_name", "label", "amount")},
    }
