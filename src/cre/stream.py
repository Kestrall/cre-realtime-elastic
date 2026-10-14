"""Publication continue de CRE et mesure du délai de restitution.

Deux mesures distinctes :
- ingest_lag_ms : délai génération -> passage dans le pipeline d'ingestion
  (calculé côté Elasticsearch, visible dans Kibana) ;
- délai de restitution : génération -> document visible par une recherche,
  qui inclut le refresh de l'index (c'est ce que voit réellement un client).
"""

from __future__ import annotations

import statistics
import time

from elasticsearch import Elasticsearch, helpers

from .generator import CreGenerator


def _actions(gen: CreGenerator, index: str, count: int):
    for _ in range(count):
        yield {"_index": index, "_source": gen.event()}


def time_to_searchable(es: Elasticsearch, gen: CreGenerator, index: str, timeout: float = 10.0) -> float:
    """Publie un CRE sonde et mesure (en ms) le temps avant qu'il soit trouvable."""
    probe = gen.event()
    start = time.perf_counter()
    es.index(index=index, document=probe)
    while time.perf_counter() - start < timeout:
        hits = es.search(index=index, query={"term": {"event_id": probe["event_id"]}}, size=0, track_total_hits=True)
        if hits["hits"]["total"]["value"]:
            return (time.perf_counter() - start) * 1000
        time.sleep(0.02)
    raise TimeoutError(f"CRE sonde {probe['event_id']} non visible après {timeout}s")


def run(es: Elasticsearch, index: str, rate: int, duration: int, probe_every: float = 2.0) -> dict:
    """Publie `rate` CRE par seconde pendant `duration` secondes."""
    gen = CreGenerator()
    sent = 0
    probes: list[float] = []
    next_probe = time.monotonic()
    end = time.monotonic() + duration

    while time.monotonic() < end:
        tick = time.monotonic()
        ok, _ = helpers.bulk(es, _actions(gen, index, rate), chunk_size=rate)
        sent += ok
        if tick >= next_probe:
            probes.append(time_to_searchable(es, gen, index))
            next_probe = tick + probe_every
            print(f"  {sent:>8} CRE publiés | restitution sonde : {probes[-1]:6.0f} ms", flush=True)
        time.sleep(max(0.0, 1.0 - (time.monotonic() - tick)))

    return {
        "sent": sent,
        "probes": len(probes),
        "restitution_p50_ms": round(statistics.median(probes)),
        "restitution_max_ms": round(max(probes)),
    }
