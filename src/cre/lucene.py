"""Inspection des fichiers Lucene d'un index, dont les Doc Values (.dvm / .dvd)."""

from __future__ import annotations

import struct
import subprocess
from collections import defaultdict
from pathlib import Path

from elasticsearch import Elasticsearch

CONTAINER = "cre-es"
DATA_DIR = "/usr/share/elasticsearch/data/indices"

# Extension -> rôle du fichier dans un segment Lucene
EXTENSIONS = {
    "dvm": "Doc Values, métadonnées (où se trouve chaque champ dans le .dvd)",
    "dvd": "Doc Values, données (stockage colonne : tri, agrégations, scripts)",
    "tim": "Dictionnaire de termes (index inversé)",
    "tip": "Index du dictionnaire de termes",
    "tmd": "Métadonnées du dictionnaire de termes",
    "doc": "Listes de documents par terme (postings)",
    "pos": "Positions des termes (requêtes de phrase)",
    "pay": "Payloads et offsets",
    "fdt": "Champs stockés (_source)",
    "fdx": "Index des champs stockés",
    "fdm": "Métadonnées des champs stockés",
    "kdd": "Arbre BKD des points (nombres, dates) : données",
    "kdi": "Arbre BKD des points : index",
    "kdm": "Arbre BKD des points : métadonnées",
    "nvd": "Norms : données (pondération du score)",
    "nvm": "Norms : métadonnées",
    "fnm": "Description des champs du segment",
    "si": "Informations du segment",
    "cfs": "Fichier composé (regroupe les fichiers d'un petit segment)",
    "cfe": "Table des entrées du fichier composé",
    "liv": "Documents supprimés",
    "psm": "Métadonnées des postings",
    "bfi": "Filtre de Bloom sur _id (spécifique Elasticsearch)",
    "bfm": "Filtre de Bloom : métadonnées",
    "segments": "Point de commit (liste des segments actifs)",
    "lock": "Verrou d'écriture",
}

CODEC_MAGIC = 0x3FD76C17


def index_uuid(es: Elasticsearch, index: str) -> str:
    settings = es.indices.get_settings(index=index)
    return settings[index]["settings"]["index"]["uuid"]


def list_files(es: Elasticsearch, index: str) -> list[tuple[str, int]]:
    """Retourne (chemin, taille) des fichiers Lucene du shard 0, lus dans le conteneur."""
    path = f"{DATA_DIR}/{index_uuid(es, index)}/0/index"
    out = subprocess.run(
        ["docker", "exec", CONTAINER, "find", path, "-type", "f", "-printf", "%s %p\\n"],
        check=True, capture_output=True, text=True,
    ).stdout
    files = []
    for line in out.splitlines():
        size, file = line.split(" ", 1)
        files.append((file, int(size)))
    return files


def sizes_by_extension(files: list[tuple[str, int]]) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for file, size in files:
        name = Path(file).name
        ext = name.rsplit(".", 1)[-1] if "." in name else name.split("_")[0]
        totals[ext] += size
    return dict(sorted(totals.items(), key=lambda kv: -kv[1]))


def read_codec_header(data: bytes) -> dict:
    """Décode l'en-tête commun à tous les fichiers Lucene (CodecUtil.writeIndexHeader).

    magic (int32) | nom du codec (vint + octets) | version (int32) | id du segment (16 octets)
    """
    magic = struct.unpack(">I", data[:4])[0]
    if magic != CODEC_MAGIC:
        raise ValueError(f"magic inattendu : {magic:#x}")
    length, pos = _read_vint(data, 4)
    codec = data[pos:pos + length].decode("utf-8")
    pos += length
    version = struct.unpack(">I", data[pos:pos + 4])[0]
    segment_id = data[pos + 4:pos + 20].hex()
    return {"codec": codec, "version": version, "segment_id": segment_id}


def _read_vint(data: bytes, pos: int) -> tuple[int, int]:
    value, shift = 0, 0
    while True:
        b = data[pos]
        pos += 1
        value |= (b & 0x7F) << shift
        if not b & 0x80:
            return value, pos
        shift += 7


def dvm_headers(es: Elasticsearch, index: str) -> list[dict]:
    """Lit l'en-tête de chaque .dvm de l'index directement dans le conteneur."""
    headers = []
    for file, size in list_files(es, index):
        if not file.endswith(".dvm"):
            continue
        raw = subprocess.run(
            ["docker", "exec", CONTAINER, "head", "-c", "128", file],
            check=True, capture_output=True,
        ).stdout
        headers.append({"file": Path(file).name, "size": size, **read_codec_header(raw)})
    return headers
