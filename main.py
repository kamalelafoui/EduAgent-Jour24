"""EduDeploy — agent d'admission HITL déployé en 4 modes (Jour 24).

API   : uvicorn main:app --host 0.0.0.0 --port 8000
CLI   : python main.py batch|stream|edge|realtime|compare|drift [fichier.csv]
Secret: aucune clé dans le code ; ADMIN_API_KEY et AGENT_API_KEY en variables d'environnement.
"""
import json
import os
import sys
from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from edudeploy import VERSION, drift, modes
from edudeploy.recommend import recommander
from edudeploy.scoring import calculer_score, categoriser

AGENT_API_KEY = os.getenv("AGENT_API_KEY", "dev-agent-key")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "dev-admin-key")
DATA = os.getenv("DOSSIERS_CSV", "data/dossiers.csv")

app = FastAPI(title="EduDeploy — modes de déploiement", version=VERSION)


def auth(x_api_key: str = Header(default="")):
    if x_api_key not in (AGENT_API_KEY, ADMIN_API_KEY):
        raise HTTPException(401, "Clé API invalide")


def admin(x_api_key: str = Header(default="")):
    if x_api_key != ADMIN_API_KEY:
        raise HTTPException(403, "Droits administrateur requis")


class Dossier(BaseModel):
    candidat_id: str = Field(min_length=1, max_length=40)
    programme: str = Field(min_length=1, max_length=60)
    moyenne: float = Field(ge=0, le=20)
    similarite_lettre_pct: float = Field(ge=0, le=100)
    diplome_verifiable: str = Field(pattern="^(oui|non)$")
    pieces_completes: str = Field(pattern="^(oui|non)$")
    cas_sensible: str = Field(pattern="^(oui|non)$")


def _d(m: Dossier):
    return {k: str(v) for k, v in m.model_dump().items()}


@app.get("/health")
def health():
    return {"status": "ok", "version": VERSION, "modes": ["batch", "real-time", "streaming", "edge"]}


@app.post("/realtime/score", dependencies=[Depends(auth)])
def realtime_score(body: Dossier):
    res, s = modes.realtime([_d(body)])
    return {"mode": "real-time", **res[0], "latence_ms": round(res[0]["latence_ms"], 1)}


@app.post("/edge/score", dependencies=[Depends(auth)])
def edge_score(body: Dossier):
    res, _ = modes.edge([_d(body)])
    return {"mode": "edge", **res[0], "latence_ms": round(res[0]["latence_ms"], 3), "donnees_quittent_appareil": False}


@app.post("/batch/run", dependencies=[Depends(auth)])
def batch_run(body: list[Dossier]):
    if not body or len(body) > 5000:
        raise HTTPException(422, "Lot de 1 à 5000 dossiers")
    res, s = modes.batch([_d(x) for x in body])
    return {"resume": s, "resultats": [{**r, "latence_ms": round(r["latence_ms"], 1)} for r in res]}


@app.post("/stream/simulate", dependencies=[Depends(auth)])
def stream_simulate(n: int = 500, debit_evt_s: int = 50):
    if not 1 <= n <= 20000:
        raise HTTPException(422, "n entre 1 et 20000")
    _, s = modes.streaming(modes.generer_dossiers(n), debit_evt_s=debit_evt_s)
    return s


@app.get("/recommend")
def recommend(latence_tolerance_ms: int, volume_par_jour: int, flux_continu: bool = False,
              connectivite: str = "stable", donnees: str = "normales"):
    return recommander(latence_tolerance_ms, volume_par_jour, flux_continu, connectivite, donnees)


@app.get("/compare", dependencies=[Depends(admin)])
def compare(n: int = 2000):
    return modes.comparer(modes.generer_dossiers(min(max(n, 10), 20000)))


@app.get("/drift", dependencies=[Depends(admin)])
def drift_report():
    return drift.analyser()


def cli():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "compare"
    src = sys.argv[2] if len(sys.argv) > 2 else DATA
    dossiers = modes.charger_csv(src) if os.path.exists(src) else modes.generer_dossiers(200)
    if cmd == "compare":
        out = modes.comparer(modes.generer_dossiers(2000))
        for m, v in out.items():
            r = v["resume"]
            print(f"{m:10} p95={r['latence_traitement_p95_ms']:>9} ms | délai résultat={r['delai_resultat_moyen_s']:>10} s | coût/1000={r['cout_1000_dossiers_usd']} $ | succès={r['taux_succes_pct']} %")
    elif cmd in ("batch", "realtime", "edge", "stream"):
        f = {"batch": modes.batch, "realtime": modes.realtime, "edge": modes.edge, "stream": modes.streaming}[cmd]
        res, s = f(dossiers)
        print(json.dumps(s, ensure_ascii=False, indent=2))
        os.makedirs("outputs", exist_ok=True)
        with open(f"outputs/{cmd}_resultats.json", "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=1)
    elif cmd == "drift":
        for w in drift.analyser():
            print(w)
    else:
        print(__doc__)


if __name__ == "__main__":
    cli()
