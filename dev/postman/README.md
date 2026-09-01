# Collection Postman — ai-agent-poc

## Import

1. Postman → **Import** → glisser les deux fichiers de ce dossier :
   - `ai-agent-poc.postman_collection.json`
   - `local.postman_environment.json`
2. En haut à droite, sélectionner l'environnement **"ai-agent-poc — local"**.
3. S'assurer que la stack tourne : `docker compose up -d` depuis `dev/`.

## Contenu

- **Epic 0 - Infra** : `GET /health`
- **Epic 1 - RAG**, à exécuter dans l'ordre (chaque requête a des tests intégrés, onglet *Test Results*) :
  1. Ingestion d'un document sur un incident de paiement
  2. Ingestion d'un document sans rapport (un chat qui dort) — sert à vérifier que la recherche distingue bien les sujets
  3. Ingestion avec contenu vide → doit être rejetée (422)
  4. Recherche reformulée sur le paiement (mots différents du document) → doit remonter le document 1, score > 0.5
  5. Recherche reformulée sur le chat → doit remonter le document 2, pas celui du paiement
  6. Recherche avec `top_k=999` → doit être rejetée (422, borne max = 50)

## Lancer toute la collection d'un coup

Bouton **Run** sur la collection (Collection Runner) — les requêtes 1 et 2 renseignent automatiquement les variables d'environnement `payment_document_id` et `cat_document_id`, utilisées par les tests des requêtes 4 et 5. Les exécuter dans le désordre casserait ces tests (variables pas encore renseignées).

## Nettoyage

Les documents créés par la collection restent en base après l'exécution (utile pour inspecter les résultats). Pour les supprimer :

```bash
docker exec dev-db-1 psql -U postgres -d ai_agent_poc -c "DELETE FROM documents WHERE id IN ('<id1>', '<id2>');"
```
