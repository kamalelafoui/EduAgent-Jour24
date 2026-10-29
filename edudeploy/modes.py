"""Simulation des 4 stratégies de déploiement. Temps VIRTUEL : les latences réseau/LLM sont modélisées
(aucun appel réel, aucun sleep), les calculs de règles sont réellement exécutés.
Hypothèses explicites : voir PARAMS."""
import csv
import random
import time
from pathlib import Path
from statistics import mean

from .scoring import calculer_score, categoriser

PARAMS = {
    "llm_ms": (900, 2200),          # latence simulée d'un appel LLM cloud
    "rtt_ms": (60, 140),            # aller-retour réseau simulé
    "p_echec_cloud": 0.03,          # taux d'échec d'un appel cloud (retry 1 fois puis revue manuelle)
    "tokens_par_dossier": 171,      # 2397 tokens / 14 dossiers (outputs/kpi_resume.json, Jour 23)
    "cout_par_dossier_usd": 0.000828 / 14,   # idem
    "remise_batch": 0.5,            # HYPOTHÈSE : remise des API batch (à vérifier selon fournisseur)
    "workers": {"realtime": 4, "batch": 16, "streaming": 8, "edge": 1},
    "fenetre_stream_ms": 500,       # micro-batch du flux
    "fenetre_batch_h": 24,          # exécution planifiée une fois par jour
    "edge_overhead_ms": (2, 6),     # surcoût appareil (chargement, I/O local)
}
CHAMPS = ["candidat_id", "programme", "moyenne", "similarite_lettre_pct", "diplome_verifiable", "pieces_completes", "cas_sensible"]


def charger_csv(chemin):
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def generer_dossiers(n, seed=7, p_fraude=0.12, p_incomplet=0.25, p_sensible=0.15):
    rng = random.Random(seed)
    progs = ["Informatique", "Médecine", "Droit", "Gestion", "Biologie"]
    out = []
    for i in range(n):
        fraude = rng.random() < p_fraude
        out.append({"candidat_id": f"SIM-{seed}-{i:05d}", "programme": rng.choice(progs),
                    "moyenne": f"{rng.uniform(9, 18):.1f}",
                    "similarite_lettre_pct": str(rng.randint(40, 70) if fraude else rng.randint(2, 25)),
                    "diplome_verifiable": "oui",
                    "pieces_completes": "non" if rng.random() < p_incomplet else "oui",
                    "cas_sensible": "oui" if rng.random() < p_sensible else "non"})
    return out


def _cloud(d, rng, seuil):
    """Un dossier traité côté cloud : RTT + LLM, 1 retry, puis revue manuelle."""
    lat = 0.0
    for tentative in range(2):
        lat += rng.uniform(*PARAMS["rtt_ms"]) + rng.uniform(*PARAMS["llm_ms"])
        if rng.random() >= PARAMS["p_echec_cloud"]:
            s = calculer_score(d)
            return {"candidat_id": d["candidat_id"], "score": s, "categorie": categoriser(s, seuil),
                    "statut": "ok", "latence_ms": lat, "tokens": PARAMS["tokens_par_dossier"]}
        lat += 200  # backoff
    return {"candidat_id": d["candidat_id"], "score": None, "categorie": categoriser(None, seuil),
            "statut": "revue_manuelle", "latence_ms": lat, "tokens": PARAMS["tokens_par_dossier"]}


def _pct(vals, p):
    v = sorted(vals)
    return v[min(len(v) - 1, int(p * len(v)))] if v else 0.0


def _resume(mode, res, duree_virtuelle_s, delai_resultat_s, cout, extra):
    lat = [r["latence_ms"] for r in res]
    ok = sum(1 for r in res if r["statut"] == "ok")
    return {"mode": mode, "n": len(res), "taux_succes_pct": round(100 * ok / len(res), 2),
            "revue_manuelle": len(res) - ok,
            "latence_traitement_p50_ms": round(_pct(lat, 0.5), 1), "latence_traitement_p95_ms": round(_pct(lat, 0.95), 1),
            "delai_resultat_moyen_s": round(delai_resultat_s, 3),
            "debit_dossiers_s": round(len(res) / duree_virtuelle_s, 2) if duree_virtuelle_s else None,
            "cout_usd": round(cout, 6), "cout_1000_dossiers_usd": round(1000 * cout / len(res), 4), **extra}


def realtime(dossiers, seed=1, seuil=70):
    rng = random.Random(seed)
    res = [_cloud(d, rng, seuil) for d in dossiers]
    w = PARAMS["workers"]["realtime"]
    duree = sum(r["latence_ms"] for r in res) / 1000 / w
    cout = len(res) * PARAMS["cout_par_dossier_usd"]
    return res, _resume("real-time", res, duree, mean(r["latence_ms"] for r in res) / 1000, cout,
                        {"donnees_quittent_appareil": True, "hors_ligne": False, "analyse_llm": True})


def batch(dossiers, seed=2, seuil=70):
    rng = random.Random(seed)
    res = [_cloud(d, rng, seuil) for d in dossiers]
    w = PARAMS["workers"]["batch"]
    duree = sum(r["latence_ms"] for r in res) / 1000 / w
    attente = PARAMS["fenetre_batch_h"] * 3600 / 2          # attente moyenne avant l'exécution planifiée
    cout = len(res) * PARAMS["cout_par_dossier_usd"] * (1 - PARAMS["remise_batch"])
    return res, _resume("batch", res, duree, attente + duree, cout,
                        {"donnees_quittent_appareil": True, "hors_ligne": False, "analyse_llm": True,
                         "fenetre_h": PARAMS["fenetre_batch_h"]})


def streaming(dossiers, seed=3, seuil=70, debit_evt_s=50):
    rng = random.Random(seed)
    res, w = [], PARAMS["workers"]["streaming"]
    fen = PARAMS["fenetre_stream_ms"]
    for d in dossiers:
        r = _cloud(d, rng, seuil)
        r["latence_ms"] += rng.uniform(0, fen)               # attente dans la fenêtre du micro-batch
        res.append(r)
    duree = max(len(res) / debit_evt_s, sum(r["latence_ms"] for r in res) / 1000 / w)
    cout = len(res) * PARAMS["cout_par_dossier_usd"]
    return res, _resume("streaming", res, duree, mean(r["latence_ms"] for r in res) / 1000, cout,
                        {"donnees_quittent_appareil": True, "hors_ligne": False, "analyse_llm": True,
                         "debit_entrant_evt_s": debit_evt_s, "fenetre_ms": fen})


def edge(dossiers, seed=4, seuil=70):
    """Règles seules, exécutées sur l'appareil : aucun réseau, aucun LLM. Journal synchronisé plus tard."""
    rng = random.Random(seed)
    res, reel = [], []
    for d in dossiers:
        t0 = time.perf_counter()
        s = calculer_score(d)
        reel.append((time.perf_counter() - t0) * 1000)
        res.append({"candidat_id": d["candidat_id"], "score": s, "categorie": categoriser(s, seuil), "statut": "ok",
                    "latence_ms": reel[-1] + rng.uniform(*PARAMS["edge_overhead_ms"]), "tokens": 0})
    duree = sum(r["latence_ms"] for r in res) / 1000
    return res, _resume("edge", res, duree, mean(r["latence_ms"] for r in res) / 1000, 0.0,
                        {"donnees_quittent_appareil": False, "hors_ligne": True, "analyse_llm": False,
                         "sync_differee_evenements": len(res), "calcul_reel_moyen_ms": round(mean(reel), 5)})


def comparer(dossiers, seuil=70):
    out = {}
    for f in (realtime, batch, streaming, edge):
        r, s = f(dossiers, seuil=seuil)
        out[s["mode"]] = {"resume": s, "categories": {c: sum(1 for x in r if x["categorie"] == c) for c in ("Risque élevé", "Risque faible")}}
    return out
