# Résultats du benchmark (1 000 000 CRE)

Exécuté le 2026-10-14T19:56:55+00:00 sur un nœud unique, 1 shard, après force merge à 1 segment.

## Vue d'ensemble

| Mesure | cre-default | cre-tuned | Écart |
|---|---:|---:|---:|
| Taille sur disque | 370.6 Mo | 264.4 Mo | -29 % |
| Doc Values (.dvd + .dvm) | 65.9 Mo | 19.2 Mo | -71 % |
| Débit d'ingestion | 23 364 CRE/s | 29 915 CRE/s | +28 % |

## Latence des requêtes (médiane sur 15 exécutions, cache désactivé)

| Requête | cre-default | cre-tuned |
|---|---:|---:|
| Volume par type d'opération | 0 ms | 0 ms |
| Montants par jour (30 j) | 14 ms | 16 ms |
| Top 10 comptes les plus actifs | 13 ms | 13 ms |
| Débit / crédit par entité | 25 ms | 27 ms |
| 50 derniers CRE (tri par date) | 21 ms | 0 ms |

## Fichiers Lucene par extension

| Extension | Rôle | cre-default | cre-tuned |
|---|---|---:|---:|
| `.fdt` | Champs stockés (_source) | 186.9 Mo | 186.9 Mo |
| `.dvd` | Doc Values, données (stockage colonne : tri, agrégations, scripts) | 65.8 Mo | 19.2 Mo |
| `.tim` | Dictionnaire de termes (index inversé) | 57.9 Mo | 34.0 Mo |
| `.doc` | Listes de documents par terme (postings) | 30.0 Mo | 12.7 Mo |
| `.kdd` | Arbre BKD des points (nombres, dates) : données | 17.0 Mo | 9.9 Mo |
| `.pos` | Positions des termes (requêtes de phrase) | 7.7 Mo | 43.0 Ko |
| `.nvd` | Norms : données (pondération du score) | 3.0 Mo | 0.0 Ko |
| `.bfi` | Filtre de Bloom sur _id (spécifique Elasticsearch) | 1.2 Mo | 1.2 Mo |
| `.tip` | Index du dictionnaire de termes | 976.2 Ko | 554.9 Ko |
| `.kdi` | Arbre BKD des points : index | 74.3 Ko | 30.8 Ko |
| `.fdx` | Index des champs stockés | 21.4 Ko | 21.3 Ko |
| `.fnm` | Description des champs du segment | 4.6 Ko | 2.9 Ko |
| `.dvm` | Doc Values, métadonnées (où se trouve chaque champ dans le .dvd) | 3.3 Ko | 2.3 Ko |
| `.tmd` | Métadonnées du dictionnaire de termes | 1.4 Ko | 0.9 Ko |
| `.si` | Informations du segment | 0.7 Ko | 0.7 Ko |
| `.nvm` | Norms : métadonnées | 0.5 Ko | 0.0 Ko |
| `.kdm` | Arbre BKD des points : métadonnées | 0.5 Ko | 0.3 Ko |
| `.fdm` | Métadonnées des champs stockés | 0.4 Ko | 0.4 Ko |
| `.segments` | Point de commit (liste des segments actifs) | 0.4 Ko | 0.4 Ko |
| `.psm` | Métadonnées des postings | 0.1 Ko | 0.1 Ko |
| `.bfm` | Filtre de Bloom : métadonnées | 0.1 Ko | 0.1 Ko |
| `.lock` | Verrou d'écriture | 0.0 Ko | 0.0 Ko |

## Doc Values par champ (API `_disk_usage`)

| Champ | cre-default | cre-tuned |
|---|---:|---:|
| `@timestamp` | 2 441 Ko | 1 954 Ko |
| `account_id` | 1 959 Ko | 1 959 Ko |
| `amount` | 3 418 Ko | 2 930 Ko |
| `balance_after` | 3 906 Ko | 3 418 Ko |
| `channel` | 488 Ko | 488 Ko |
| `city` | 488 Ko | 488 Ko |
| `currency` | 0 Ko | 0 Ko |
| `direction` | 122 Ko | 122 Ko |
| `entity` | 244 Ko | 244 Ko |
| `event_id` | 35 282 Ko | 0 Ko |
| `generated_at` | 2 441 Ko | 0 Ko |
| `holder_name` | 977 Ko | 0 Ko |
| `iban` | 2 058 Ko | 0 Ko |
| `ingest_lag_ms` | 3 906 Ko | 3 419 Ko |
| `ingested_at` | 1 818 Ko | 1 466 Ko |
| `label` | 4 246 Ko | 0 Ko |
| `merchant_category` | 435 Ko | 435 Ko |
| `operation_type` | 488 Ko | 488 Ko |
| `status` | 244 Ko | 244 Ko |

## En-têtes des fichiers .dvm

- `cre-default` / `_2c_Lucene90_0.dvm` (3417 octets) : codec `Lucene90DocValuesMetadata`, version 0, segment `9dc6b0a00d93a28d069c36e8e9479295`
- `cre-tuned` / `_29_Lucene90_0.dvm` (2403 octets) : codec `Lucene90DocValuesMetadata`, version 0, segment `9dc6b0a00d93a28d069c36e8e9479299`
