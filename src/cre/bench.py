"""Benchmark : mapping dynamique (par défaut) contre mapping optimisé autour des Doc Values."""

from __future__ import annotations

import json
import statistics
import time
from datetime import datetime, timedelta, timezone

from elasticsearch import Elasticsearch, helpers

from . import lucene
from .es import INDEX_DEFAULT, INDEX_TUNED, ROOT, setup
from .generator import CreGenerator

STRING_FIELDS = {"account_id", "entity", "operation_type", "direction", "channel",
                 "merchant_category", "city", "status", "event_id", "iban"}


def field(index: str, name: str) -> str:
    """Le mapping dynamique indexe les chaînes en text + sous-champ .keyword."""
    return f"{name}.keyword" if index == INDEX_DEFAULT and name in STRING_FIELDS else name


def queries(index: str) -> dict[str, dict]:
    f = lambda name: field(index, name)  # noqa: E731
    return {
        "Volume par type d'opération": {
            "size": 0, "aggs": {"ops": {"terms": {"field": f("operation_type")}}},
        },
        "Montants par jour (30 j)": {
            "size": 0, "aggs": {"jours": {"date_histogram": {"field": "@timestamp", "calendar_interval": "day"},
                                          "aggs": {"total": {"sum": {"field": "amount"}}}}},
        },
        "Top 10 comptes les plus actifs": {
            "size": 0, "aggs": {"comptes": {"terms": {"field": f("account_id"), "size": 10}}},
        },
        "Débit / crédit par entité": {
            "size": 0, "aggs": {"entites": {"terms": {"field": f("entity")},
                                            "aggs": {"sens": {"terms": {"field": f("direction")},
                                                              "aggs": {"total": {"sum": {"field": "amount"}}}}}}},
        },
        "50 derniers CRE (tri par date)": {
            "size": 50, "sort": [{"@timestamp": "desc"}], "track_total_hits": False,
        },
    }


def ingest(es: Elasticsearch, docs: int, chunk: int = 5000) -> dict[str, float]:
    """Indexe les mêmes CRE dans les deux index, étalés sur 30 jours."""
    gen = CreGenerator(seed=42)
    start = datetime.now(timezone.utc) - timedelta(days=30)
    step = timedelta(days=30) / docs
    elapsed = {INDEX_DEFAULT: 0.0, INDEX_TUNED: 0.0}

    for n, offset in enumerate(range(0, docs, chunk)):
        batch = [gen.event(now=start + step * i) for i in range(offset, min(offset + chunk, docs))]
        # Ordre alterné pour ne favoriser aucun index (cache disque, JIT).
        for index in (list(elapsed) if n % 2 == 0 else list(reversed(elapsed))):
            t = time.perf_counter()
            helpers.bulk(es, ({"_index": index, "_source": doc} for doc in batch), chunk_size=chunk)
            elapsed[index] += time.perf_counter() - t
        print(f"  {min(offset + chunk, docs):>9} / {docs} CRE indexés", end="\r", flush=True)
    print()
    return {index: round(docs / seconds) for index, seconds in elapsed.items()}


def query_latency(es: Elasticsearch, index: str, runs: int = 15) -> dict[str, float]:
    results = {}
    for name, body in queries(index).items():
        took = [es.search(index=index, request_cache=False, **body)["took"] for _ in range(runs)]
        results[name] = statistics.median(took)
    return results


def disk_usage(es: Elasticsearch, index: str) -> dict:
    usage = es.indices.disk_usage(index=index, run_expensive_tasks=True)[index]
    return {
        "total": usage["store_size_in_bytes"],
        "fields": {
            name: {
                "doc_values": stats["doc_values_in_bytes"],
                "inverted_index": stats["inverted_index"]["total_in_bytes"],
                "points": stats["points_in_bytes"],
                "stored": stats["stored_fields_in_bytes"],
                "norms": stats["norms_in_bytes"],
            }
            for name, stats in usage["fields"].items()
        },
    }


def run(es: Elasticsearch, docs: int) -> dict:
    setup(es, reset=True)
    print(f"Ingestion de {docs} CRE dans {INDEX_DEFAULT} et {INDEX_TUNED}...")
    throughput = ingest(es, docs)

    print("Refresh, force merge à 1 segment, flush...")
    for index in (INDEX_DEFAULT, INDEX_TUNED):
        es.indices.refresh(index=index)
        es.indices.forcemerge(index=index, max_num_segments=1, wait_for_completion=True)
        es.indices.flush(index=index)

    report = {"docs": docs, "date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "indices": {}}
    for index in (INDEX_DEFAULT, INDEX_TUNED):
        print(f"Mesures sur {index}...")
        files = lucene.list_files(es, index)
        report["indices"][index] = {
            "ingest_docs_per_s": throughput[index],
            "store_bytes": es.indices.stats(index=index, metric="store")["indices"][index]["primaries"]["store"]["size_in_bytes"],
            "lucene_files": lucene.sizes_by_extension(files),
            "dvm_headers": lucene.dvm_headers(es, index),
            "disk_usage": disk_usage(es, index),
            "query_ms": query_latency(es, index),
        }

    out = ROOT / "results" / "bench.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (ROOT / "results" / "bench.md").write_text(to_markdown(report), encoding="utf-8")
    return report


def _mb(n: int) -> str:
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} Ko"
    return f"{n / 1024 / 1024:.1f} Mo"


def to_markdown(report: dict) -> str:
    d, t = report["indices"][INDEX_DEFAULT], report["indices"][INDEX_TUNED]
    gain = lambda a, b: f"{(b - a) / a * 100:+.0f} %" if a else "n/a"  # noqa: E731
    lines = [
        f"# Résultats du benchmark ({report['docs']:,} CRE)".replace(",", " "),
        "",
        f"Exécuté le {report['date']} sur un nœud unique, 1 shard, après force merge à 1 segment.",
        "",
        "## Vue d'ensemble",
        "",
        f"| Mesure | {INDEX_DEFAULT} | {INDEX_TUNED} | Écart |",
        "|---|---:|---:|---:|",
        f"| Taille sur disque | {_mb(d['store_bytes'])} | {_mb(t['store_bytes'])} | {gain(d['store_bytes'], t['store_bytes'])} |",
        f"| Doc Values (.dvd + .dvm) | {_mb(d['lucene_files'].get('dvd', 0) + d['lucene_files'].get('dvm', 0))} "
        f"| {_mb(t['lucene_files'].get('dvd', 0) + t['lucene_files'].get('dvm', 0))} "
        f"| {gain(d['lucene_files'].get('dvd', 0), t['lucene_files'].get('dvd', 0))} |",
        f"| Débit d'ingestion | {d['ingest_docs_per_s']:,} CRE/s | {t['ingest_docs_per_s']:,} CRE/s "
        f"| {gain(d['ingest_docs_per_s'], t['ingest_docs_per_s'])} |".replace(",", " "),
        "",
        "## Latence des requêtes (médiane sur 15 exécutions, cache désactivé)",
        "",
        f"| Requête | {INDEX_DEFAULT} | {INDEX_TUNED} |",
        "|---|---:|---:|",
    ]
    lines += [f"| {q} | {d['query_ms'][q]:.0f} ms | {t['query_ms'][q]:.0f} ms |" for q in d["query_ms"]]
    lines += ["", "## Fichiers Lucene par extension", "",
              f"| Extension | Rôle | {INDEX_DEFAULT} | {INDEX_TUNED} |", "|---|---|---:|---:|"]
    exts = sorted(set(d["lucene_files"]) | set(t["lucene_files"]),
                  key=lambda e: -max(d["lucene_files"].get(e, 0), t["lucene_files"].get(e, 0)))
    for e in exts:
        role = lucene.EXTENSIONS.get(e, "")
        lines.append(f"| `.{e}` | {role} | {_mb(d['lucene_files'].get(e, 0))} | {_mb(t['lucene_files'].get(e, 0))} |")

    lines += ["", "## Doc Values par champ (API `_disk_usage`)", "",
              f"| Champ | {INDEX_DEFAULT} | {INDEX_TUNED} |", "|---|---:|---:|"]
    names = sorted({n.removesuffix(".keyword") for n in d["disk_usage"]["fields"]} | set(t["disk_usage"]["fields"]))
    for n in names:
        if n.startswith("_"):
            continue
        dv_d = sum(v["doc_values"] for k, v in d["disk_usage"]["fields"].items() if k.removesuffix(".keyword") == n)
        dv_t = t["disk_usage"]["fields"].get(n, {}).get("doc_values", 0)
        lines.append(f"| `{n}` | {dv_d / 1024:,.0f} Ko | {dv_t / 1024:,.0f} Ko |".replace(",", " "))

    lines += ["", "## En-têtes des fichiers .dvm", ""]
    for index in (INDEX_DEFAULT, INDEX_TUNED):
        for h in report["indices"][index]["dvm_headers"]:
            lines.append(f"- `{index}` / `{h['file']}` ({h['size']} octets) : codec `{h['codec']}`, "
                         f"version {h['version']}, segment `{h['segment_id']}`")
    return "\n".join(lines) + "\n"
