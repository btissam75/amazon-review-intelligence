<div align="center">

# Amazon Review Intelligence

### From one million customer reviews to explainable product decisions

An end-to-end data and machine-learning platform that replays Amazon reviews as a real-time
stream, predicts customer sentiment with NLP, builds product intelligence, and serves
personalized recommendations through a polished analytics experience.

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Apache Kafka](https://img.shields.io/badge/Apache_Kafka-4.1-231F20?logo=apachekafka)](https://kafka.apache.org/)
[![Apache Spark](https://img.shields.io/badge/Apache_Spark-4.2-E25A1C?logo=apachespark&logoColor=white)](https://spark.apache.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-8.0-47A248?logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-1.0_API-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue.js](https://img.shields.io/badge/Vue.js-3-4FC08D?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![Docker](https://img.shields.io/badge/Docker_Compose-ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

**[Dashboard](http://localhost:3000)** · **[Interactive API](http://localhost:8000/docs)** · **[Technical report](outputs/rapport_pipeline_1_million.md)**

</div>

---

## Executive summary

Amazon Review Intelligence is a portfolio-grade implementation of a complete ML data product—not
just a notebook or a standalone classifier. It connects data quality, event streaming, distributed
processing, NLP inference, recommender systems, API design, and product-oriented visualization in
one reproducible architecture.

The application guides users through a coherent decision journey:

1. **Understand** global customer sentiment and rating patterns.
2. **Explore** named products, metadata, quality scores, and real customer comments.
3. **Analyze** any review with live three-class sentiment inference.
4. **Decide** with personalized, explainable Top-10 recommendations.

> **Real-time scope:** the source is the reproducible Amazon Reviews 2023 public dataset. Historical
> events are replayed through Kafka to simulate a production event stream; the project does not
> scrape Amazon's live website or bypass access controls.

## Proven scale

| Outcome | Verified result |
|---|---:|
| Reviews processed and stored | **1,000,000** |
| Product intelligence profiles | **154,311** |
| Products enriched with names and metadata | **154,294 (99.989%)** |
| Users with personalized Top-10 recommendations | **121,812** |
| Kafka partitions for review topics | **8** |
| NLP training sample | **150,000 balanced reviews** |
| Chronological NLP test set | **30,000 reviews** |
| Sentiment macro-F1 | **0.757** |
| Automated Python tests in the validated run | **14 passed** |

Observed sentiment distribution on the one-million-review run:

| Sentiment | Reviews | Average confidence |
|---|---:|---:|
| Positive | 674,808 | 0.864 |
| Negative | 163,429 | 0.764 |
| Neutral | 161,763 | 0.654 |

Detailed evidence and methodology are available in the
[one-million-review validation report](outputs/rapport_pipeline_1_million.md).

## Architecture

```mermaid
flowchart LR
    A[Amazon Reviews 2023] --> B[Validation & normalization]
    B -->|valid JSONL| C[Replay producer]
    B -->|invalid records| DLQ1[Local DLQ]
    C -->|product_id key| K[(Kafka · 8 partitions)]
    K --> S[Spark Structured Streaming]
    S -->|invalid events| DLQ2[amazon.reviews.dlq]
    S -->|NLP-enriched events| E[amazon.reviews.enriched]
    S -->|idempotent upserts| M[(MongoDB)]
    M --> P[Product intelligence profiles]
    P --> R[Spark ALS + NLP re-ranking]
    R --> M
    M --> API[FastAPI]
    API --> UI[Vue 3 decision dashboard]
```

## What makes this project distinctive

### Streaming that survives real failures

- Kafka topics are provisioned automatically and partitioned by `product_id`.
- Spark Structured Streaming limits micro-batches to 20,000 events.
- Invalid events are preserved in a dead-letter topic instead of silently discarded.
- MongoDB writes are idempotent, retryable, and safe to resume.
- Spark checkpoints preserve stream progress across container restarts.
- The metadata importer resumes after truncated gzip/network streams and skips completed work.
- Recommendation generation resumes from already materialized users after interruption.

### NLP designed as a measurable component

- Weak labels are generated from ratings: 1–2 negative, 3 neutral, 4–5 positive.
- Class-wise reservoir sampling produces a balanced 150k sample without loading the corpus in memory.
- A chronological split makes evaluation closer to future production behavior.
- TF-IDF unigram/bigram features feed a class-weighted logistic regression model.
- Each prediction includes a label, confidence score, model name, and model version.
- Spark and FastAPI use the same serialized inference pipeline.

| Class | F1-score |
|---|---:|
| Negative | 0.773 |
| Neutral | 0.639 |
| Positive | 0.857 |
| **Macro average** | **0.757** |

### Hybrid recommendations, not a popularity list

Spark ALS learns collaborative preferences from user–product interactions. Candidates are
re-ranked with customer sentiment and popularity:

```text
hybrid_score = 0.65 × ALS affinity
             + 0.25 × NLP-backed product quality
             + 0.10 × normalized popularity
```

Product quality combines confidence-adjusted sentiment, average rating, and verified-purchase
ratio. Recommendations carry human-readable reasons. Cold-start users receive a quality/popularity
fallback rather than an error.

The recommender also includes a leakage-controlled offline benchmark. For every eligible user,
the chronologically latest interaction is hidden, while ALS and NLP product-quality signals are
rebuilt from earlier interactions only. The same users are evaluated against four strategies:
popularity, NLP quality, ALS, and the production hybrid. The report exposes Precision@10,
Recall/HitRate@10, NDCG@10, MRR@10, catalog coverage, category diversity, and novelty.

### A user-facing ML product

The Vue interface is organized around **Understand → Explore → Analyze → Decide** and includes:

- global sentiment and rating visualizations;
- product discovery by name, brand, category, or reference;
- product images, prices, features, descriptions, and representative comments;
- one-click transfer of a real review into the live NLP laboratory;
- personalized recommendations with score decomposition;
- human-friendly demo profiles with technical IDs hidden behind an advanced control;
- responsive dark/light themes and a dedicated pipeline health view.

## Technology choices

| Layer | Technology | Responsibility |
|---|---|---|
| Data contracts | Pydantic | Validation, normalization, schema versioning |
| Event transport | Apache Kafka 4.1 | Partitioned review stream and DLQ |
| Stream processing | Spark Structured Streaming 4.2 | Validation, deduplication, batch NLP inference |
| NLP | scikit-learn | TF-IDF + weighted logistic regression |
| Recommendations | Spark MLlib ALS | Collaborative filtering and candidate generation |
| Serving store | MongoDB 8 | Reviews, profiles, recommendations, registry |
| API | FastAPI | Analytics, product discovery, inference, recommendations |
| Web application | Vue 3, TypeScript, Vite, ECharts | Interactive decision experience |
| Runtime | Docker Compose | Reproducible multi-service environment |

## MongoDB serving model

| Collection | Purpose |
|---|---|
| `reviews_enriched` | Canonical reviews with sentiment and model traceability |
| `product_profiles` | Aggregated quality, sentiment, verification, and product metadata |
| `user_recommendations` | Materialized personalized Top-10 per eligible user |
| `recommendation_fallbacks` | Quality/popularity selection for cold-start users |
| `recommendation_evaluations` | Temporal benchmark and comparable ranking metrics |
| `model_registry` | Model version, weights, training status, and document counts |
| `pipeline_jobs` | Resumable enrichment progress and operational status |

## Quick start

### Prerequisites

- Docker Desktop with Docker Compose
- Git
- Python 3.11+ for local preparation and tests
- At least 8 GB of memory available to Docker for the complete pipeline

### 1. Clone and install

```bash
git clone https://github.com/btissam75/amazon-review-intelligence.git
cd amazon-review-intelligence
python -m venv .venv
```

```powershell
.venv\Scripts\Activate.ps1
pip install -e ".[nlp,streaming,api,dev]"
```

### 2. Prepare one million validated reviews

Source archives are streamed and are not committed to Git.

```powershell
ari-prepare download --category All_Beauty --limit 600000 --output data/clean/reviews_All_Beauty.jsonl --dlq data/clean/reviews_All_Beauty.dlq.jsonl --report data/reports/quality_All_Beauty.json
ari-prepare download --category Appliances --limit 400000 --output data/clean/reviews_Appliances.jsonl --dlq data/clean/reviews_Appliances.dlq.jsonl --report data/reports/quality_Appliances.json
```

Use a smaller `--limit` for a fast local smoke test.

### 3. Train the sentiment model

```powershell
ari-train-baseline --input-pattern "data/clean/reviews_*.jsonl" --max-per-class 50000
```

This creates `models/sentiment_baseline.joblib` and a report under `data/reports/`. Models and
datasets are intentionally excluded from Git.

### 4. Start and feed the streaming pipeline

```powershell
docker compose up -d --build kafka kafka-init mongodb spark-streaming
docker compose --profile ingest run --rm producer
```

```powershell
docker compose logs -f spark-streaming
```

### 5. Build recommendation and product intelligence

Run these after Spark has materialized the review corpus:

```powershell
docker compose --profile recommendation build recommender
docker compose --profile recommendation run --rm recommender
docker compose --profile metadata build metadata-enricher
docker compose --profile metadata run --rm metadata-enricher
```

### 6. Launch the product

```powershell
docker compose up -d --build api frontend
```

- Dashboard: <http://localhost:3000>
- OpenAPI/Swagger: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/analytics/overview | ConvertTo-Json -Depth 5
```

### 7. Build the human-reviewed gold dataset

Create a balanced sample of 500 reviews per weak class. Twenty percent of the tasks require two
independent annotations so that inter-annotator agreement can be measured with Cohen's kappa.

```powershell
docker compose run --rm api python -m amazon_review_intelligence.annotation.bootstrap
```

Open <http://localhost:3000/annotations>. The annotation screen deliberately hides the Amazon
rating and model prediction until the human decision is saved. Conflicting double annotations can
be adjudicated from the same interface. Ambiguous reviews can be marked `uncertain`; they are
excluded from the gold export until an expert adjudicates them.

Export only completed consensus/adjudicated records:

```powershell
docker compose run --rm api python -m amazon_review_intelligence.annotation.export
```

The command writes `data/annotations/reviewed_reviews.jsonl` and
`data/reports/annotation_report.json`. The report includes completion, conflicts, class
distribution, double-annotation coverage, and Cohen's kappa.

### 8. Evaluate NLP against human decisions

Once reviewed annotations have been exported, evaluate the exact serialized model served by the
API. The command calculates accuracy, Macro-F1, per-class precision/recall/F1, confidence
statistics, disagreement analysis, and the confusion matrix.

```powershell
docker compose run --rm api python -m amazon_review_intelligence.nlp.evaluate_human
```

Results are written to `data/reports/nlp_human_evaluation.json` and
`data/reports/nlp_confusion_matrix.png`, persisted in `nlp_evaluations`, exposed by FastAPI, and
shown in the dashboard. The report always includes the evaluated human-corpus size, preventing a
partial annotation sample from being mistaken for the final benchmark.

### 9. Enrich sentiment by product aspect

The aspect pipeline detects quality, price, delivery, packaging, durability, and usability at
sentence level. It applies the serialized sentiment model only to relevant sentences, stores
evidence and confidence with every review, and can safely resume after interruption.

```powershell
docker compose --profile aspects build aspect-enricher
docker compose --profile aspects run --rm aspect-enricher
```

This historical backfill may take time on one million reviews. Progress is persisted in the
`pipeline_jobs` collection, while already versioned reviews are skipped on every restart. New
Kafka events receive the same enrichment directly in Spark Structured Streaming.

### 10. Evaluate recommendation quality

Run the temporal leave-last-one-out benchmark after the cleaned corpus and sentiment model are
available. This job is isolated from serving and never overwrites production recommendations.

```powershell
docker compose --profile evaluation build recommender-evaluation
docker compose --profile evaluation run --rm recommender-evaluation
```

The result is stored in MongoDB, attached to `hybrid-als-nlp-v1` in the model registry, written to
`data/reports/recommender_evaluation.json`, exposed by the API, and rendered in the dashboard.

## API surface

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Database and recommendation-model readiness |
| `GET` | `/api/v1/analytics/overview` | Corpus, product, user, and model KPIs |
| `GET` | `/api/v1/analytics/sentiments` | Sentiment distribution and confidence |
| `GET` | `/api/v1/analytics/details` | Ratings, verified purchases, categories |
| `GET` | `/api/v1/analytics/aspects` | Aspect sentiment globally or for one product |
| `GET` | `/api/v1/products` | Paginated search and quality filtering |
| `GET` | `/api/v1/products/{product_id}` | Product intelligence and customer reviews |
| `GET` | `/api/v1/users/sample` | Demonstration profiles for the UI |
| `GET` | `/api/v1/annotations/progress` | Gold-dataset progress and agreement |
| `GET` | `/api/v1/annotations/next` | Next blinded annotation task |
| `POST` | `/api/v1/annotations/{review_id}` | Save an independent human label |
| `GET` | `/api/v1/annotations/conflicts/next` | Next task requiring adjudication |
| `POST` | `/api/v1/annotations/{review_id}/adjudicate` | Resolve an annotation conflict |
| `GET` | `/api/v1/nlp/evaluation` | Sentiment metrics against human-reviewed labels |
| `GET` | `/api/v1/recommendations/evaluation` | Temporal offline recommender benchmark |
| `GET` | `/api/v1/recommendations/{user_id}` | Personalized or cold-start Top-10 |
| `GET` | `/api/v1/recommendations` | Global fallback ranking |
| `POST` | `/api/v1/sentiment/predict` | Live sentiment inference |
| `POST` | `/api/v1/sentiment/aspects` | Sentence-level aspect sentiment and evidence |

Example:

```bash
curl -X POST http://localhost:8000/api/v1/sentiment/predict \
  -H "Content-Type: application/json" \
  -d '{"text":"Excellent quality and very easy to use."}'
```

## Testing and quality gates

```powershell
pytest
ruff check src tests
python -m compileall -q src
docker compose config --quiet
cd frontend
npm ci
npm run typecheck
npm run build
```

Tests cover event normalization, preparation, chronological NLP splitting, inference, API
behavior, bounded hybrid scoring, and explainable recommendation reasons.

## Repository structure

```text
amazon-review-intelligence/
├── frontend/                         # Vue 3 decision dashboard
├── infrastructure/                   # Dockerfiles and Nginx configuration
├── src/amazon_review_intelligence/
│   ├── api/                          # FastAPI routes and schemas
│   ├── data/                         # Preparation, profiling, metadata enrichment
│   ├── nlp/                          # Training and shared inference
│   ├── recommendation/               # Spark ALS and hybrid scoring
│   └── streaming/                    # Kafka producer and Spark job
├── tests/                            # Automated unit and API tests
├── outputs/                          # Specifications and validation reports
├── docker-compose.yml                # Complete local platform
└── pyproject.toml                    # Python package and CLI entry points
```

## Engineering decisions

- **Replay instead of live scraping:** reproducible experiments, stable schemas, and respectful
  use of the public research dataset.
- **MongoDB as the serving layer:** Spark computes; the API reads indexed, materialized documents.
- **Materialized recommendations:** predictable API latency and model-version traceability.
- **Idempotency by design:** review and recommendation upserts allow safe retries.
- **Chronological evaluation:** reduces optimistic leakage compared with a random-only split.
- **Transparent baseline first:** measurable behavior and fast distributed inference before a
  more expensive Transformer.

## Limitations and roadmap

This project reports measured results without presenting the baseline as a finished production
model. Rating-derived labels contain noise, and the neutral class remains the main weakness.

Planned extensions:

- DistilBERT/DeBERTa comparison on a manually reviewed evaluation subset;
- aspect-based sentiment for price, quality, delivery, packaging, and durability;
- data-quality, confidence, and temporal-drift monitoring;
- recommender evaluation with NDCG@K and Recall@K;
- authentication, rate limiting, CI/CD, observability, and deployment manifests;
- multilingual sentiment and localized product experiences.

## Data provenance and responsible use

The project uses [Amazon Reviews 2023](https://amazon-reviews-2023.github.io/main.html), published
by the McAuley Lab for research. Content and metadata remain subject to the dataset's original
terms. Datasets, generated models, checkpoints, and database volumes are excluded from Git.

This repository is an engineering and research demonstration. Recommendations should not drive
consequential decisions without further validation, bias analysis, privacy review, and monitoring.

## Project documentation

- [Functional and technical specification](outputs/cahier_des_charges_amazon_nlp.md)
- [One-million-review validation report](outputs/rapport_pipeline_1_million.md)
- [Initial delivery progress report](outputs/rapport_avancement_lot1.md)

---

<div align="center">

Built by **[Btissam Arehal](https://github.com/btissam75)** as an end-to-end demonstration of
data engineering, distributed ML, backend engineering, and product-focused analytics.

</div>
