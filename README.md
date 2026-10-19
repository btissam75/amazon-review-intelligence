# Amazon Review Intelligence

Pipeline de données temps réel centré sur l'analyse NLP des sentiments dans les avis Amazon.

## État actuel

Le **Lot 1 — Données** fournit :

- un contrat versionné pour les événements ;
- un téléchargement en streaming depuis Amazon Reviews 2023 ;
- une préparation JSONL reproductible ;
- une validation stricte et une dead-letter queue locale ;
- un rapport de qualité calculé sans charger tout le corpus en mémoire.

## Installation locale

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[nlp,dev]"
```

## Préparer les données

Téléchargement direct en streaming depuis Hugging Face :

```powershell
ari-prepare download --category All_Beauty --limit 50000
```

Ou normaliser un fichier JSONL/JSONL.GZ déjà disponible :

```powershell
ari-prepare file data/raw/reviews.jsonl.gz --limit 50000
```

Résultats :

- `data/clean/reviews.jsonl` : événements valides ;
- `data/clean/reviews.dlq.jsonl` : lignes rejetées et motifs ;
- `data/reports/quality_report.json` : profil qualité.

Pour recalculer un rapport :

```powershell
ari-profile data/clean/reviews.jsonl
```

## Tests

```powershell
pytest
```

## Baseline NLP

La note sert uniquement à créer une étiquette faible : 1–2 négatif, 3 neutre, 4–5 positif.
La baseline utilise TF-IDF (unigrammes et bigrammes) et une régression logistique pondérée.

```powershell
ari-train-baseline --input-pattern "data/clean/reviews_*.jsonl" --max-per-class 50000
```

Elle écrit le modèle dans `models/sentiment_baseline.joblib` et les métriques détaillées dans
`data/reports/baseline_metrics.json`. La séparation est chronologique afin de mieux représenter
une utilisation future en production.

La source principale est [Amazon Reviews 2023](https://amazon-reviews-2023.github.io/main.html),
publiée par le McAuley Lab. Le temps réel sera simulé par rejeu chronologique dans Kafka.

## Pipeline Kafka → Spark → MongoDB

Le service Spark lit `amazon.reviews.raw`, applique le modèle de sentiment, publie dans
`amazon.reviews.enriched` et effectue des upserts idempotents dans MongoDB.

```powershell
docker compose up -d --build kafka kafka-init mongodb spark-streaming
docker compose --profile ingest run --rm producer
```

Le producteur est configuré pour publier jusqu’à 1 000 000 d’avis à 5 000 événements/seconde.
Les checkpoints Spark sont persistés dans `data/checkpoints`.

