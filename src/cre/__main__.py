"""Point d'entrée : python -m cre <commande>."""

from __future__ import annotations

import argparse
import json

from . import anonymize, bench, kibana, lucene, stream
from .es import INDEX_TUNED, client, setup


def main() -> None:
    parser = argparse.ArgumentParser(prog="cre", description="Lab CRE temps réel sur Elasticsearch")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("setup", help="crée les pipelines et les index")
    p.add_argument("--reset", action="store_true", help="supprime et recrée les index")

    p = sub.add_parser("stream", help="publie des CRE en continu")
    p.add_argument("--index", default=INDEX_TUNED)
    p.add_argument("--rate", type=int, default=500, help="CRE par seconde")
    p.add_argument("--duration", type=int, default=60, help="durée en secondes")

    p = sub.add_parser("bench", help="compare mapping par défaut et mapping optimisé")
    p.add_argument("--docs", type=int, default=1_000_000)

    p = sub.add_parser("anonymize", help="crée le jeu hors production réduit et pseudonymisé")
    p.add_argument("--pct", type=int, default=10, help="pourcentage de comptes conservés")

    sub.add_parser("kibana", help="importe les vues de données et le tableau de bord Kibana")

    p = sub.add_parser("lucene", help="liste les fichiers Lucene d'un index")
    p.add_argument("--index", default=INDEX_TUNED)

    args = parser.parse_args()
    es = client()

    if args.cmd == "setup":
        setup(es, reset=args.reset)
        print("Pipelines et index prêts.")
    elif args.cmd == "stream":
        setup(es)
        print(json.dumps(stream.run(es, args.index, args.rate, args.duration), indent=2, ensure_ascii=False))
    elif args.cmd == "bench":
        bench.run(es, args.docs)
        print("Rapport écrit dans results/bench.md")
    elif args.cmd == "anonymize":
        print(json.dumps(anonymize.run(es, args.pct), indent=2, ensure_ascii=False))
    elif args.cmd == "kibana":
        print(f"Tableau de bord : {kibana.setup()}")
    elif args.cmd == "lucene":
        for ext, size in lucene.sizes_by_extension(lucene.list_files(es, args.index)).items():
            print(f"  .{ext:<9} {size / 1024 / 1024:8.2f} Mo  {lucene.EXTENSIONS.get(ext, '')}")
        for h in lucene.dvm_headers(es, args.index):
            print(f"  {h['file']} : codec {h['codec']} v{h['version']}")


if __name__ == "__main__":
    main()
