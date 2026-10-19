# Rapport d’avancement — Lot 1 Données et baseline NLP

Date : 19 octobre 2026

## Réalisé

- Structure Python du projet et configuration des dépendances.
- Contrat canonique versionné des événements d’avis.
- Téléchargement en streaming du corpus Amazon Reviews 2023 sans conserver l’archive complète.
- Normalisation du schéma, nettoyage HTML/Unicode et horodatage UTC.
- Identifiants déterministes, empreintes de contenu et déduplication.
- Fichier dead-letter pour les événements invalides.
- Rapport automatique de qualité des données.
- Création des classes de sentiment à partir des notes pour la supervision faible.
- Baseline TF-IDF + régression logistique, séparation chronologique et rapport d’évaluation.
- Dix tests automatisés validés.

## Validation sur données réelles

Un essai contrôlé a été exécuté sur 100 avis de la catégorie `All_Beauty` :

- 100 événements valides ;
- 0 événement rejeté ;
- 0 doublon ;
- 99 produits uniques ;
- distribution : 6 avis à 1 étoile, 4 à 2 étoiles, 10 à 3 étoiles, 35 à 4 étoiles et 45 à 5 étoiles.

La baseline entraînée sur seulement 80 avis et testée sur 20 obtient un macro-F1 de 0,382. Ce résultat n’est pas une mesure finale : l’échantillon minuscule et fortement déséquilibré sert uniquement à vérifier l’exécution complète. L’entraînement pertinent doit utiliser au minimum plusieurs dizaines de milliers d’avis.

## Étape suivante

Préparer l’échantillon reproductible de 50 000 avis, analyser son équilibre, entraîner la baseline complète, puis construire et comparer le modèle Transformer.
