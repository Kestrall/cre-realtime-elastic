# Doc Values : ce qu'il y a dans les fichiers `.dvm` et `.dvd`

## Le problème que résolvent les Doc Values

L'index inversé de Lucene répond vite à la question « quels documents contiennent ce terme ? ». Il est en revanche très mauvais pour la question inverse : « quelle est la valeur du champ `amount` pour le document 42 ? ». Or c'est exactement ce dont ont besoin :

- les **agrégations** (somme des montants par jour, top des comptes) ;
- le **tri** (les 50 derniers CRE) ;
- les **scripts** qui lisent `doc['champ']` (comme l'échantillonnage par compte du module d'anonymisation).

Les Doc Values sont un **stockage en colonnes**, écrit sur disque au moment de l'indexation : pour chaque champ, la liste des valeurs dans l'ordre des documents. Elasticsearch les lit via le cache de pages du système, sans les charger dans le tas Java.

## Deux fichiers par segment

| Fichier | Contenu | Taille typique |
|---|---|---|
| `.dvd` (*Doc Values Data*) | Les valeurs encodées et compressées, champ par champ | Gros : des dizaines de Mo ici |
| `.dvm` (*Doc Values Metadata*) | Pour chaque champ : type de Doc Values, encodage choisi, position et longueur de ses blocs dans le `.dvd`, nombre de valeurs | Minuscule : 2 à 4 Ko ici |

À l'ouverture d'un segment, Lucene lit **entièrement** le `.dvm` en mémoire : c'est la table des matières qui lui permet ensuite d'aller lire directement la bonne zone du `.dvd`.

Les deux fichiers commencent par l'en-tête commun de Lucene, que le module `cre.lucene` décode :

```
magic 0x3FD76C17 | nom du codec | version | identifiant du segment (16 octets) | suffixe
```

Sur ce lab, le nom du codec lu est `Lucene90DocValuesMetadata` pour le `.dvm` (et `Lucene90DocValuesData` pour le `.dvd`).

## Les types de Doc Values

Lucene propose cinq types de Doc Values :

| Type | Usage |
|---|---|
| `NUMERIC` | Une valeur numérique par document |
| `SORTED` | Un terme par document, stocké comme un numéro d'ordre dans un dictionnaire trié |
| `SORTED_NUMERIC` | Plusieurs nombres par document |
| `SORTED_SET` | Plusieurs termes par document |
| `BINARY` | Octets bruts |

Elasticsearch, lui, n'en utilise principalement que deux, car tout champ peut devenir multi-valué :

| Type de champ Elasticsearch | Doc Values Lucene | Exemples dans les CRE |
|---|---|---|
| Nombres, dates, `scaled_float` | `SORTED_NUMERIC` | `amount`, `@timestamp`, `balance_after` |
| `keyword` | `SORTED_SET` | `operation_type`, `entity`, `account_id` |

Quand un champ n'a en pratique qu'une seule valeur par document, le codec `Lucene90` le détecte au moment de l'écriture et l'encode de façon aussi compacte qu'un `NUMERIC` ou un `SORTED`. C'est cette information (encodage choisi, nombre de valeurs, emplacement des blocs) qui est consignée dans le `.dvm`.

Conséquence pratique : un champ `keyword` à **faible cardinalité** (7 types d'opération, 4 entités) ne coûte presque rien, car chaque document ne stocke qu'un petit numéro d'ordre. Un champ à **forte cardinalité** comme `event_id` (un UUID unique par CRE) coûte très cher : le dictionnaire contient autant de termes que de documents.

## Ce que montre le benchmark

Sur 1 million de CRE (voir [`results/bench.md`](../results/bench.md)) :

- `event_id` pèse à lui seul **35 Mo de Doc Values** dans le mapping par défaut, plus de la moitié du `.dvd`. Il ne sert pourtant qu'à retrouver un CRE précis, ce que l'index inversé fait très bien. Avec `doc_values: false`, il tombe à 0.
- Même logique pour `iban`, `holder_name`, `label` et `generated_at` : ils sont lus ou recherchés, jamais agrégés ni triés.
- Les champs qui servent aux tableaux de bord (`operation_type`, `entity`, `amount`, `@timestamp`) gardent leurs Doc Values : les agrégations ont la même latence dans les deux index.
- Au total, le `.dvd` passe de **66 à 19 Mo (−71 %)** et l'index entier de **371 à 264 Mo (−29 %)**, avec un débit d'ingestion supérieur, car il y a moins de structures à écrire.

## Le tri d'index, l'autre usage des Doc Values

L'index optimisé est trié par `@timestamp` décroissant (`index.sort`). Lucene range alors les documents de chaque segment dans cet ordre, ce qui permet d'arrêter la recherche dès les N premiers résultats trouvés (*early termination*). La requête « 50 derniers CRE » passe de 21 ms à moins d'une milliseconde : c'est le cas d'usage typique d'une restitution temps réel (« les dernières opérations de ce client »).

Ce tri a un coût à l'indexation et impose que le champ de tri ait des Doc Values.

## Règles de décision retenues

1. **Agrégé, trié ou lu par un script ?** Doc Values activées.
2. **Uniquement recherché par valeur exacte ?** `keyword` avec `doc_values: false`.
3. **Uniquement recherché en plein texte ?** `text` ou `match_only_text` (pas de positions ni de norms si le score n'a pas d'importance).
4. **Seulement affiché ?** `index: false` et `doc_values: false` : il reste dans `_source`.
5. **Valeur constante ?** `constant_keyword` : ni index, ni Doc Values.

Attention : désactiver les Doc Values est **irréversible sans réindexation**. Si un jour on veut agréger par IBAN, il faudra réindexer. C'est pourquoi chaque choix est documenté dans le mapping.
