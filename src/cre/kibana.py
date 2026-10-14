"""Vues de données et tableau de bord Kibana, importés par l'API saved objects."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid

KIBANA_URL = os.environ.get("KIBANA_URL", "http://localhost:5601")
DATA_VIEW_ID = "cre-tuned"
DASHBOARD_ID = "cre-temps-reel"

DATA_VIEWS = [
    {"id": "cre-tuned", "title": "cre-tuned", "name": "CRE temps réel"},
    {"id": "cre-hors-prod", "title": "cre-hors-prod", "name": "CRE hors production (anonymisé)"},
]


def _request(method: str, path: str, body: bytes | None = None, content_type: str = "application/json") -> dict:
    req = urllib.request.Request(f"{KIBANA_URL}{path}", data=body, method=method,
                                 headers={"kbn-xsrf": "true", "Content-Type": content_type})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


# ---------- Colonnes Lens ----------

def _date(label: str = "@timestamp") -> dict:
    return {"label": label, "dataType": "date", "operationType": "date_histogram", "sourceField": "@timestamp",
            "isBucketed": True, "scale": "interval", "params": {"interval": "auto", "includeEmptyRows": True}}


def _count(label: str) -> dict:
    return {"label": label, "customLabel": True, "dataType": "number", "operationType": "count",
            "sourceField": "___records___", "isBucketed": False, "scale": "ratio"}


def _metric(op: str, field: str, label: str) -> dict:
    return {"label": label, "customLabel": True, "dataType": "number", "operationType": op,
            "sourceField": field, "isBucketed": False, "scale": "ratio"}


def _terms(field: str, label: str, order_by: str, size: int = 10) -> dict:
    return {"label": label, "customLabel": True, "dataType": "string", "operationType": "terms",
            "sourceField": field, "isBucketed": True, "scale": "ordinal",
            "params": {"size": size, "orderBy": {"type": "column", "columnId": order_by},
                       "orderDirection": "desc", "otherBucket": True, "missingBucket": False}}


def _lens(obj_id: str, title: str, vis_type: str, columns: dict, visualization: dict) -> dict:
    return {
        "type": "lens", "id": obj_id, "typeMigrationVersion": "8.9.0", "coreMigrationVersion": "8.8.0",
        "attributes": {
            "title": title, "description": "", "visualizationType": vis_type,
            "state": {
                "datasourceStates": {"formBased": {"layers": {"l1": {"columns": columns, "columnOrder": list(columns)}}}},
                "visualization": visualization,
                "query": {"query": "", "language": "kuery"}, "filters": [],
            },
        },
        "references": [{"type": "index-pattern", "id": DATA_VIEW_ID, "name": "indexpattern-datasource-layer-l1"}],
    }


def _metric_panel(obj_id: str, title: str, column: dict) -> dict:
    return _lens(obj_id, title, "lnsMetric", {"m": column},
                 {"layerId": "l1", "layerType": "data", "metricAccessor": "m"})


def _xy(obj_id: str, title: str, columns: dict, x: str, y: list[str], series: str, split: str | None = None) -> dict:
    layer = {"layerId": "l1", "layerType": "data", "seriesType": series, "xAccessor": x, "accessors": y}
    if split:
        layer["splitAccessor"] = split
    return _lens(obj_id, title, "lnsXY", columns, {
        "preferredSeriesType": series, "layers": [layer],
        "legend": {"isVisible": True, "position": "right"}, "valueLabels": "hide",
    })


def visualizations() -> list[tuple[dict, dict]]:
    """(objet Lens, position sur la grille du tableau de bord de 48 colonnes)."""
    return [
        (_metric_panel("cre-kpi-volume", "CRE reçus", _count("CRE reçus")), {"x": 0, "y": 0, "w": 12, "h": 7}),
        (_metric_panel("cre-kpi-montant", "Montant total (EUR)", _metric("sum", "amount", "Montant total (EUR)")),
         {"x": 12, "y": 0, "w": 12, "h": 7}),
        (_metric_panel("cre-kpi-lag", "Délai d'ingestion médian (ms)",
                       _metric("median", "ingest_lag_ms", "Délai d'ingestion médian (ms)")),
         {"x": 24, "y": 0, "w": 12, "h": 7}),
        (_metric_panel("cre-kpi-comptes", "Comptes actifs", _metric("unique_count", "account_id", "Comptes actifs")),
         {"x": 36, "y": 0, "w": 12, "h": 7}),
        (_xy("cre-flux", "Flux de CRE par type d'opération",
             {"t": _date(), "op": _terms("operation_type", "Type d'opération", "n", 7), "n": _count("CRE")},
             x="t", y=["n"], series="bar_stacked", split="op"),
         {"x": 0, "y": 7, "w": 32, "h": 14}),
        (_lens("cre-canaux", "Répartition par canal", "lnsPie",
               {"c": _terms("channel", "Canal", "n", 5), "n": _count("CRE")},
               {"shape": "donut", "layers": [{"layerId": "l1", "layerType": "data", "primaryGroups": ["c"],
                                              "metrics": ["n"], "numberDisplay": "percent",
                                              "categoryDisplay": "default", "legendDisplay": "default"}]}),
         {"x": 32, "y": 7, "w": 16, "h": 14}),
        (_xy("cre-entites", "Montants par entité et par sens",
             {"e": _terms("entity", "Entité", "s", 4), "d": _terms("direction", "Sens", "s", 2),
              "s": _metric("sum", "amount", "Montant (EUR)")},
             x="e", y=["s"], series="bar_horizontal", split="d"),
         {"x": 0, "y": 21, "w": 24, "h": 13}),
        (_xy("cre-lag", "Délai d'ingestion (médiane et 99e centile, ms)",
             {"t": _date(), "p50": _metric("median", "ingest_lag_ms", "Médiane"),
              "p99": {**_metric("percentile", "ingest_lag_ms", "99e centile"), "params": {"percentile": 99}}},
             x="t", y=["p50", "p99"], series="line"),
         {"x": 24, "y": 21, "w": 24, "h": 13}),
    ]


def dashboard(panels: list[tuple[dict, dict]]) -> dict:
    panels_json, references = [], []
    for obj, grid in panels:
        pid = str(uuid.uuid5(uuid.NAMESPACE_URL, obj["id"]))
        panels_json.append({"type": "lens", "panelIndex": pid, "gridData": {**grid, "i": pid},
                            "embeddableConfig": {"hidePanelTitles": True} if obj["attributes"]["visualizationType"] == "lnsMetric" else {},
                            "panelRefName": f"panel_{pid}"})
        references.append({"type": "lens", "id": obj["id"], "name": f"{pid}:panel_{pid}"})
    return {
        "type": "dashboard", "id": DASHBOARD_ID, "typeMigrationVersion": "8.9.0", "coreMigrationVersion": "8.8.0",
        "attributes": {
            "title": "CRE temps réel", "description": "Restitution temps réel des comptes rendus d'événements",
            "panelsJSON": json.dumps(panels_json), "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": False}),
            "timeRestore": True, "timeFrom": "now-15m", "timeTo": "now",
            "refreshInterval": {"pause": False, "value": 5000},
            "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})},
        },
        "references": references,
    }


def setup() -> str:
    for view in DATA_VIEWS:
        _request("POST", "/api/data_views/data_view", json.dumps({
            "data_view": {**view, "timeFieldName": "@timestamp"}, "override": True,
        }).encode())
    # Ancienne vue globale cre-* : elle mélangeait les index et triplait les chiffres.
    try:
        _request("DELETE", "/api/data_views/data_view/cre")
    except urllib.error.HTTPError:
        pass

    panels = visualizations()
    ndjson = "\n".join(json.dumps(o) for o in [obj for obj, _ in panels] + [dashboard(panels)]) + "\n"
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"cre.ndjson\"\r\n"
            f"Content-Type: application/ndjson\r\n\r\n{ndjson}\r\n--{boundary}--\r\n").encode()
    result = _request("POST", "/api/saved_objects/_import?overwrite=true", body,
                      content_type=f"multipart/form-data; boundary={boundary}")
    if not result.get("success"):
        raise RuntimeError(json.dumps(result.get("errors"), indent=2, ensure_ascii=False))
    return f"{KIBANA_URL}/app/dashboards#/view/{DASHBOARD_ID}"
