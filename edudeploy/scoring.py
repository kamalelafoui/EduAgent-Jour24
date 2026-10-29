"""Règles de scoring de l'agent d'admission HITL (identiques au projet Jour 23)."""
SEUIL_HITL = 70


def calculer_score(d):
    score = 10
    if float(d["similarite_lettre_pct"]) >= 40 or str(d["diplome_verifiable"]).strip().lower() == "non":
        score += 60
    if str(d["pieces_completes"]).strip().lower() == "non":
        score += 30
    if str(d["cas_sensible"]).strip().lower() == "oui":
        score += 20
    return min(score, 100)


def categoriser(score, seuil=SEUIL_HITL):
    """Score absent ou >= seuil : risque élevé (escalade par défaut)."""
    return "Risque élevé" if score is None or score >= seuil else "Risque faible"
