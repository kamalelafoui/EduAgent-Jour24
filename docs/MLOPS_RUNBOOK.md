# Runbook MLOps — dérive de performance
| Étape | Action | Critère |
|---|---|---|
| Détection | `python main.py drift` ou GET /drift | rappel « risque élevé » < 85 % ou PSI > 0,2 |
| Contention | Augmenter l'échantillon relu par la commission ; Kill Switch si dérive grave | décisions humaines prioritaires |
| Remédiation | Analyser les cas manqués ; proposer règle/seuil (demande de changement) | cas ajoutés aux golden |
| Validation | Tests golden + approbation des 2 rôles (workflow Jour 23) | 0 écart de catégorie |
| Rétablissement | Déploiement SemVer minor + surveillance renforcée ; rollback si besoin | rappel >= 85 % deux semaines de suite |
