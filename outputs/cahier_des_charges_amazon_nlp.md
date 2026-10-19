# Cahier des charges — Analyse temps réel des avis Amazon

## 1. Présentation du projet

### 1.1 Intitulé

**Plateforme temps réel d’analyse des sentiments dans les avis Amazon**

### 1.2 Finalité

Construire une plateforme Big Data capable d’ingérer un flux continu d’avis produits, de contrôler leur qualité, de les analyser avec des modèles NLP, de conserver les résultats et de les exposer par une API.

Le système doit permettre de répondre notamment aux questions suivantes :

- Quel est le sentiment global associé à un produit ou une catégorie ?
- Comment ce sentiment évolue-t-il dans le temps ?
- Quels aspects du produit sont appréciés ou critiqués (prix, qualité, livraison, batterie, emballage, etc.) ?
- Quels avis sont incohérents avec leur note ou potentiellement suspects ?
- Quels produits connaissent une hausse soudaine d’avis négatifs ?

## 2. Objectifs

### 2.1 Objectif principal

Mettre en œuvre une chaîne de traitement temps réel allant de la donnée brute à une prédiction NLP consultable via FastAPI.

### 2.2 Objectifs fonctionnels

1. Importer un corpus public d’avis Amazon.
2. Rejouer les avis dans l’ordre chronologique pour simuler un flux temps réel.
3. Publier les événements dans Apache Kafka.
4. Valider, nettoyer et dédupliquer les événements avec Spark Structured Streaming.
5. Détecter la langue de chaque avis.
6. Prédire son sentiment : négatif, neutre ou positif.
7. Produire un score de confiance et conserver la version du modèle.
8. Détecter les aspects évoqués et, dans une seconde phase, leur sentiment.
9. Agréger les tendances par produit, catégorie et fenêtre temporelle.
10. Enregistrer les avis bruts, nettoyés et enrichis dans MongoDB.
11. Exposer les résultats au moyen d’une API REST FastAPI.
12. Fournir des indicateurs de santé, des métriques et des tests automatisés.

### 2.3 Objectifs non fonctionnels

- Tous les composants doivent être démarrables avec Docker Compose.
- Les traitements doivent être reproductibles et configurables par variables d’environnement.
- Un événement ne doit pas être comptabilisé deux fois.
- Un événement invalide doit être conservé dans une file dédiée plutôt que perdu.
- Les données, modèles et résultats doivent être traçables.
- Le dépôt ne doit contenir aucun secret.

## 3. Périmètre

### 3.1 Version MVP

- Une catégorie Amazon pour le développement initial.
- Un échantillon local de 50 000 avis.
- Rejeu configurable de 10 à 1 000 événements par seconde.
- Analyse de sentiment en trois classes.
- Agrégations temporelles et par produit.
- Stockage MongoDB.
- API de consultation et endpoint de prédiction.
- Infrastructure Docker Compose.

### 3.2 Version avancée

- Plusieurs catégories et plusieurs langues.
- Analyse de sentiment par aspect (ABSA).
- Détection d’émotions.
- Résumé automatique des points positifs et négatifs.
- Détection d’anomalies et d’avis potentiellement suspects.
- Tableau de bord temps réel et alertes.
- Registre de modèles, suivi des expériences et surveillance de la dérive.

### 3.3 Hors périmètre initial

- Contournement des protections techniques d’Amazon.
- Collecte de données personnelles non publiques.
- Classification définitive d’un avis comme frauduleux sans vérité terrain.
- Entraînement d’un grand modèle de langage à partir de zéro.

## 4. Données

### 4.1 Source principale

Le projet utilise **Amazon Reviews 2023 (McAuley Lab)**, qui fournit les textes, notes, horodatages, votes d’utilité et métadonnées produit. La source est figée afin de garantir la reproductibilité. Le temps réel est simulé par rejeu chronologique.

Le scraping éventuel est un connecteur optionnel séparé. Il ne doit être activé que pour une source dont les conditions d’utilisation et les règles d’accès l’autorisent.

### 4.2 Couches de données

- **Raw** : copie immuable de l’événement reçu.
- **Clean** : événement validé, normalisé et dédupliqué.
- **Enriched** : résultat NLP et attributs calculés.
- **Aggregate** : indicateurs par produit, catégorie et fenêtre temporelle.
- **Dead-letter** : événements rejetés avec la cause du rejet.

### 4.3 Contrat d’événement brut

```json
{
  "event_id": "uuid",
  "review_id": "string",
  "product_id": "string",
  "user_id": "string|null",
  "rating": 4.0,
  "title": "Good product",
  "text": "Works well, but the battery is weak.",
  "verified_purchase": true,
  "helpful_vote": 7,
  "category": "Appliances",
  "review_timestamp": "2023-08-15T14:32:10Z",
  "ingestion_timestamp": "2026-10-19T12:00:00Z",
  "source": "amazon_reviews_2023",
  "schema_version": 1
}
```

### 4.4 Contrat d’enrichissement NLP

```json
{
  "review_id": "string",
  "language": "en",
  "sentiment_label": "negative",
  "sentiment_score": 0.94,
  "sentiment_probabilities": {
    "negative": 0.94,
    "neutral": 0.04,
    "positive": 0.02
  },
  "rating_sentiment_mismatch": true,
  "aspects": [
    {"name": "battery", "sentiment": "negative", "score": 0.91}
  ],
  "model_name": "configured-model",
  "model_version": "1",
  "processed_at": "2026-10-19T12:00:02Z"
}
```

### 4.5 Règles de qualité

- `review_id`, `product_id`, `text` et `review_timestamp` obligatoires.
- Note comprise entre 1 et 5.
- Horodatages normalisés en UTC.
- Suppression des balises HTML et normalisation Unicode.
- Texte vide ou trop court envoyé vers la file de rejet selon la règle configurée.
- Déduplication par `review_id`, puis par empreinte du contenu si nécessaire.
- Conservation du texte original ; le nettoyage NLP produit un champ distinct.
- Rapport de qualité : taux de valeurs manquantes, doublons, rejets et langues.

## 5. Pipeline de données

```text
Dataset public / connecteur autorisé
              |
              v
      Producteur de rejeu
              |
              v
     Kafka: reviews.raw
              |
              v
 Spark Structured Streaming
   | validation / nettoyage
   | déduplication / watermark
   | inférence NLP par lots
   | agrégations fenêtrées
   |
   +--> reviews.clean
   +--> reviews.enriched
   +--> reviews.dlq
   +--> MongoDB
              |
              v
           FastAPI
```

### 5.1 Topics Kafka

- `amazon.reviews.raw`
- `amazon.reviews.clean`
- `amazon.reviews.enriched`
- `amazon.reviews.dlq`

Les messages sont partitionnés par `product_id` pour conserver l’ordre relatif des avis d’un produit.

### 5.2 Traitement Spark

- Lecture Kafka avec schéma explicite.
- Validation des types et règles métier.
- Watermark sur l’heure de l’avis pour gérer les événements tardifs.
- Déduplication par `review_id`.
- Nettoyage minimal avant NLP.
- Inférence par lots plutôt qu’une prédiction Python ligne par ligne.
- Agrégations sur fenêtres glissantes.
- Checkpoints persistants pour permettre la reprise.
- Écriture idempotente dans MongoDB via une clé unique.

### 5.3 Collections MongoDB

- `reviews_raw`
- `reviews_enriched`
- `sentiment_aggregates`
- `processing_errors`
- `model_registry`

Index principaux : `review_id` unique, `product_id`, `category`, `review_timestamp`, `sentiment_label` et index composé produit/date.

## 6. NLP — composant prioritaire

### 6.1 Tâche principale

Classification du sentiment en trois classes :

- `negative` ;
- `neutral` ;
- `positive`.

La note en étoiles sert de supervision faible pour construire les étiquettes initiales :

- 1–2 étoiles : négatif ;
- 3 étoiles : neutre ;
- 4–5 étoiles : positif.

Cette règle ne doit pas être utilisée comme prédiction finale. Elle sert à produire un jeu d’entraînement, puis un échantillon est vérifié manuellement afin de mesurer le bruit des étiquettes.

### 6.2 Méthode expérimentale

1. Analyse exploratoire et contrôle des classes.
2. Séparation par produit et par date afin de limiter les fuites de données.
3. Baseline TF-IDF + régression logistique.
4. Fine-tuning d’un Transformer adapté à la langue choisie.
5. Comparaison sur le même jeu de test figé.
6. Calibration des probabilités et analyse des erreurs.
7. Export du meilleur modèle pour l’inférence.

Pour un corpus anglais, un modèle compact de type DistilBERT est suffisant pour le MVP. Pour un corpus multilingue ou français, un Transformer multilingue ou CamemBERT sera évalué. Le choix définitif dépendra des langues observées dans les données.

### 6.3 Prétraitement NLP

- Conservation de la négation, de la ponctuation utile et des emojis.
- Suppression du HTML et des caractères de contrôle.
- Normalisation des espaces et de l’Unicode.
- Troncature contrôlée selon le tokenizer du modèle.
- Aucune suppression aveugle des stopwords pour les Transformers.
- Détection de langue avant le routage vers le modèle approprié.

### 6.4 Évaluation

Mesures obligatoires :

- macro-F1, mesure principale ;
- F1 par classe ;
- précision et rappel ;
- matrice de confusion ;
- exactitude ;
- temps d’inférence, débit et latence p95 ;
- Expected Calibration Error ou Brier score pour la confiance.

Objectifs MVP :

- macro-F1 au moins égal à 0,80 sur le jeu de test figé ;
- aucune classe avec un F1 inférieur à 0,65 ;
- débit d’au moins 100 avis/seconde sur la machine cible, à ajuster après mesure ;
- traçabilité systématique du modèle et de sa version.

### 6.5 Analyse avancée

L’analyse par aspect constitue le second lot NLP. Elle extrait les caractéristiques du produit, associe une polarité à chacune et autorise un avis globalement positif à contenir un aspect négatif, par exemple : « excellent écran, mais batterie faible ».

Aspects génériques initiaux : qualité, prix, livraison, emballage, facilité d’utilisation, performance, durabilité et service client. Des aspects propres à chaque catégorie seront ensuite découverts ou annotés.

### 6.6 Contrôle des biais et limites

- Documenter le déséquilibre entre catégories et notes.
- Évaluer séparément les langues et catégories principales.
- Ne pas assimiler automatiquement une note à l’opinion exprimée.
- Ne pas présenter la détection d’avis suspects comme une preuve de fraude.
- Stocker la confiance et permettre le statut `uncertain` sous un seuil configurable.

## 7. API FastAPI

Endpoints prévus :

- `GET /health`
- `GET /metrics`
- `POST /predict`
- `GET /reviews`
- `GET /reviews/{review_id}`
- `GET /products/{product_id}/sentiment`
- `GET /categories/{category}/trends`
- `GET /alerts`
- `GET /models/current`

L’API doit valider les entrées, paginer les listes, documenter les réponses avec OpenAPI et ne jamais exposer les identifiants utilisateurs bruts.

## 8. Architecture technique

- Python 3.11+
- Apache Kafka
- Apache Spark Structured Streaming
- MongoDB
- FastAPI et Uvicorn
- scikit-learn pour la baseline
- Transformers/PyTorch pour le modèle avancé
- Pydantic pour les contrats
- Docker et Docker Compose
- Pytest pour les tests
- Prometheus/Grafana en option avancée

## 9. Organisation du dépôt

```text
amazon-review-intelligence/
├── data/
│   ├── sample/
│   └── schemas/
├── ingestion/
├── streaming/
├── nlp/
│   ├── training/
│   ├── inference/
│   └── evaluation/
├── api/
├── dashboard/
├── infrastructure/
├── tests/
├── notebooks/
├── docs/
├── docker-compose.yml
├── .env.example
└── README.md
```

## 10. Sécurité et conformité

- Utiliser un dataset public documenté comme source initiale.
- Ne pas collecter de données derrière une authentification ni contourner un mécanisme de protection.
- Anonymiser ou hacher les identifiants utilisateurs.
- Centraliser les secrets dans les variables d’environnement.
- Limiter le débit d’un éventuel connecteur web autorisé.
- Documenter la provenance, la licence et la date d’acquisition des données.

## 11. Tests et critères d’acceptation

Le MVP est accepté si :

1. `docker compose up` démarre les services essentiels.
2. Le producteur publie un échantillon chronologique dans Kafka.
3. Spark valide et traite le flux sans perdre silencieusement les événements invalides.
4. Le redémarrage du traitement ne crée pas de doublons dans MongoDB.
5. Chaque avis valide obtient une langue, un sentiment, une confiance et une version de modèle.
6. Les métriques NLP sont calculées sur un jeu de test séparé.
7. FastAPI retourne les avis et tendances avec une documentation OpenAPI.
8. Les tests unitaires et d’intégration critiques réussissent.
9. Le README explique l’installation, l’architecture, les limites et une démonstration complète.

## 12. Plan de réalisation

### Lot 1 — Données

- téléchargement contrôlé ;
- échantillonnage reproductible ;
- profilage ;
- schémas Pydantic/JSON Schema ;
- nettoyage et rapport de qualité.

### Lot 2 — NLP hors ligne

- création des étiquettes ;
- baseline ;
- fine-tuning ;
- évaluation et export du modèle.

### Lot 3 — Streaming

- Kafka et producteur de rejeu ;
- Spark Structured Streaming ;
- topics de sortie, DLQ et checkpoints.

### Lot 4 — Persistance et API

- collections et index MongoDB ;
- endpoints FastAPI ;
- agrégations et tendances.

### Lot 5 — Industrialisation

- Docker Compose ;
- tests de bout en bout ;
- métriques et documentation ;
- démonstration reproductible.

### Lot 6 — Extensions NLP

- sentiment par aspect ;
- résumé ;
- anomalies et alertes ;
- multilingue.

## 13. Livrables

- Code source complet.
- Échantillon ou procédure reproductible d’acquisition des données.
- Modèle entraîné ou procédure de téléchargement/versionnement.
- Pipeline Kafka/Spark/MongoDB.
- API FastAPI documentée.
- Fichiers Docker.
- Tests et rapport de performance.
- Rapport d’évaluation NLP.
- Documentation technique et guide de démonstration.

## 14. Définition de réussite

Le projet est réussi lorsque l’envoi d’un avis dans Kafka provoque automatiquement sa validation, son analyse NLP, son stockage et sa disponibilité dans FastAPI, avec une latence mesurée, un résultat traçable et des métriques NLP démontrant la qualité du modèle.
