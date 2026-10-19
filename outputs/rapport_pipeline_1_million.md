# Rapport — Pipeline d’un million d’avis

Date : 19 octobre 2026

## Corpus préparé

- `All_Beauty` : 600 000 avis valides, 108 099 produits, 6 128 rejets.
- `Appliances` : 400 000 avis valides, 46 212 produits, 1 821 rejets.
- Total destiné au pipeline : **1 000 000 d’avis valides**.
- Taille des deux fichiers propres : environ 722 Mo.

Les rejets sont conservés séparément et ne sont pas comptés dans le million valide.

## Modèle NLP

La baseline a été réentraînée sur un échantillon équilibré de 150 000 avis obtenu par
échantillonnage réservoir sur le corpus complet :

- entraînement : 120 000 avis ;
- test chronologique : 30 000 avis ;
- accuracy : 0,755 ;
- macro-F1 : **0,757** ;
- F1 négatif : 0,773 ;
- F1 neutre : 0,639 ;
- F1 positif : 0,857.

La classe neutre est la plus difficile et sera la priorité du modèle Transformer.

## Pipeline implémenté

1. Le producteur lit le million d’avis et publie dans `amazon.reviews.raw`, avec `product_id`
   comme clé Kafka, compression gzip, accusé de réception complet et débit configurable.
2. Spark Structured Streaming lit huit partitions Kafka et limite chaque micro-lot à 20 000
   événements.
3. Spark valide les événements, applique un watermark de sept jours et déduplique par
   `review_id`.
4. Les événements invalides sont publiés dans `amazon.reviews.dlq`.
5. Le modèle NLP produit `sentiment_label`, `sentiment_score`, `model_name` et `model_version`.
6. Chaque micro-lot enrichi est publié dans `amazon.reviews.enriched` et écrit par upsert
   idempotent dans MongoDB.
7. Les checkpoints Spark sont persistés afin de permettre la reprise.

## Validation

- 10 tests Python réussis.
- Sources Python compilées sans erreur.
- Configuration Docker Compose validée.
- Le démarrage des conteneurs reste bloqué localement car le service privilégié Docker Desktop
  est arrêté et la session actuelle n’a pas le droit Windows de le démarrer.

## Commandes de lancement

Une fois Docker Desktop démarré :

```powershell
docker compose up -d --build kafka kafka-init mongodb spark-streaming
docker compose --profile ingest run --rm producer
```

La seconde commande publie exactement 1 000 000 d’avis à un débit cible de 5 000 événements
par seconde.
