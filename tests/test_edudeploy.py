import pytest
from fastapi.testclient import TestClient
import main
from edudeploy import drift, modes
from edudeploy.recommend import recommander
from edudeploy.scoring import calculer_score, categoriser

A = {"X-API-Key": "dev-agent-key"}; ADM = {"X-API-Key": "dev-admin-key"}
OK = {"candidat_id": "T1", "programme": "Droit", "moyenne": 12, "similarite_lettre_pct": 50,
      "diplome_verifiable": "oui", "pieces_completes": "oui", "cas_sensible": "non"}


def test_scoring_frontiere():
    d = {"similarite_lettre_pct": "50", "diplome_verifiable": "oui", "pieces_completes": "oui", "cas_sensible": "non"}
    assert calculer_score(d) == 70 and categoriser(70) == "Risque élevé" and categoriser(69) == "Risque faible"
    assert categoriser(None) == "Risque élevé"


@pytest.mark.parametrize("args,mode", [
    ((1000, 3000, False, "stable", "normales"), "real-time"),
    ((8 * 3600 * 1000, 5000, False, "stable", "normales"), "batch"),
    ((500, 500_000, True, "stable", "normales"), "streaming"),
    ((1000, 200, False, "aucune", "normales"), "edge"),
    ((1000, 200, False, "stable", "maximale"), "edge")])
def test_recommandation(args, mode):
    assert recommander(*args)["mode"] == mode


def test_memes_categories_dans_tous_les_modes():
    d = modes.generer_dossiers(300)
    base = {m: [x["categorie"] for x in f(d, seuil=70)[0]] for m, f in
            (("rt", modes.realtime), ("ba", modes.batch), ("st", modes.streaming), ("ed", modes.edge))}
    # l'edge n'a aucun échec : sert de référence ; les écarts ne viennent que des replis « revue manuelle » (élevé par défaut)
    for m in ("rt", "ba", "st"):
        for c_edge, c in zip(base["ed"], base[m]):
            assert c == c_edge or c == "Risque élevé"


def test_edge_hors_ligne_aucun_appel_cloud(monkeypatch):
    monkeypatch.setattr(modes, "_cloud", lambda *a, **k: (_ for _ in ()).throw(AssertionError("réseau appelé")))
    res, s = modes.edge(modes.generer_dossiers(50))
    assert s["hors_ligne"] and not s["donnees_quittent_appareil"] and s["cout_usd"] == 0 and len(res) == 50


def test_repli_revue_manuelle_si_echec_cloud(monkeypatch):
    monkeypatch.setitem(modes.PARAMS, "p_echec_cloud", 1.0)
    res, s = modes.realtime(modes.generer_dossiers(20))
    assert s["taux_succes_pct"] == 0 and all(r["categorie"] == "Risque élevé" and r["statut"] == "revue_manuelle" for r in res)


def test_batch_moins_cher_et_delai_long():
    d = modes.generer_dossiers(300)
    _, b = modes.batch(d); _, r = modes.realtime(d)
    assert b["cout_usd"] < r["cout_usd"] and b["delai_resultat_moyen_s"] > 3600 > r["delai_resultat_moyen_s"]


def test_derive_performance_visible_pas_la_derive_donnees():
    w = drift.analyser()
    assert w[0]["rappel_pct"] > 90 and w[-1]["rappel_pct"] < 85 and w[-1]["alerte_rappel"]
    assert all(x["psi_scores"] < drift.SEUIL_PSI for x in w)   # le PSI seul ne détecte pas cette dérive


def test_api_securite_et_modes():
    c = TestClient(main.app)
    assert c.get("/health").status_code == 200
    assert c.post("/edge/score", json=OK).status_code == 401
    assert c.post("/edge/score", headers=A, json=OK).json()["categorie"] == "Risque élevé"
    assert c.post("/realtime/score", headers=A, json={**OK, "diplome_verifiable": "peut-être"}).status_code == 422
    assert c.get("/compare", headers=A).status_code == 403
    assert set(c.get("/compare?n=50", headers=ADM).json()) == {"real-time", "batch", "streaming", "edge"}
    assert c.get("/recommend?latence_tolerance_ms=500&volume_par_jour=10").json()["mode"] == "real-time"
    assert c.post("/batch/run", headers=A, json=[]).status_code == 422
