# EduDeploy — Jour 24 : modes de déploiement de l'agent d'admission
Même agent (scoring HITL du Jour 23) déployé en Batch, Real-Time, Streaming et Edge.
```
pip install -r requirements.txt
python main.py compare            # comparaison des 4 modes (2 000 dossiers simulés)
python main.py batch data/dossiers.csv
python main.py drift              # surveillance MLOps (simulée)
python simulate.py                # produit outputs/results.json + graphiques
pytest -q                         # 12 tests
uvicorn main:app --port 8000      # API : /realtime/score /edge/score /batch/run /stream/simulate /recommend /compare /drift
docker compose up --build         # api ; docker compose --profile batch run batch
```
Dashboard : ouvrir `outputs/dashboard_modes.html` dans un navigateur (page autonome : logo, menu, comparaison des modes, formulaire d'analyse d'un dossier avec les règles de `edudeploy/scoring.py`, dérive MLOps).

Latences, taux d'échec et remise batch sont **simulés** (hypothèses dans `edudeploy/modes.py`, `PARAMS`).
