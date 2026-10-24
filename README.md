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

## Recommandations hybrides ALS + NLP

Le job de recommandation entraîne Spark ALS sur les interactions utilisateur-produit, construit
des profils produits à partir des sentiments stockés dans MongoDB, puis reclasse les candidats
avec 65 % de personnalisation ALS, 25 % de qualité NLP et 10 % de popularité. Les Top-10 sont
matérialisés dans `user_recommendations`; `recommendation_fallbacks` sert les utilisateurs sans
historique suffisant.

```powershell
docker compose --profile recommendation build recommender
docker compose --profile recommendation run --rm recommender
```

Collections produites :

- `product_profiles` : note, sentiment, confiance, achats vérifiés et score qualité ;
- `user_recommendations` : Top-10 personnalisé et raisons explicables ;
- `recommendation_fallbacks` : meilleurs produits pour le démarrage à froid ;
- `model_registry` : version, pondérations et état du modèle.

## API FastAPI

L'API expose les indicateurs NLP, les profils produits, les recommandations personnalisées et
une prédiction de sentiment à la demande.

```powershell
docker compose up -d --build api
```

Points d'entrée principaux :

- `GET /health`
- `GET /api/v1/analytics/overview`
- `GET /api/v1/analytics/sentiments`
- `GET /api/v1/products`
- `GET /api/v1/products/{product_id}`
- `GET /api/v1/recommendations/{user_id}`
- `GET /api/v1/recommendations`
- `POST /api/v1/sentiment/predict`

Documentation interactive : <http://localhost:8000/docs>.

## Dashboard Vue 3

Le dashboard utilisateur fournit une vue d'ensemble, des graphiques NLP, un catalogue de
produits, les recommandations personnalisées, un laboratoire d'inférence et l'état du pipeline.

```powershell
docker compose up -d --build frontend
```

Interface : <http://localhost:3000>. Le service démarre automatiquement l'API et MongoDB.

