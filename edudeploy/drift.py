"""Surveillance MLOps : dérive des données (PSI) ET performance IA (rappel sur décisions de la commission).
Le jeu de production est simulé : une part croissante de dossiers à risque suit un schéma que les règles ne voient pas
(« les habitudes des fraudeurs évoluent »)."""
import math
import random

from .modes import generer_dossiers
from .scoring import calculer_score, categoriser

BUCKETS = [(0, 20), (20, 35), (35, 50), (50, 65), (65, 80), (80, 101)]
SEUIL_PSI = 0.2
SEUIL_RAPPEL = 0.85


def psi(ref, cur):
    def dist(v):
        n = len(v)
        return [max(sum(1 for x in v if a <= x < b) / n, 1e-4) for a, b in BUCKETS]
    p, q = dist(ref), dist(cur)
    return sum((b - a) * math.log(b / a) for a, b in zip(p, q))


def fenetre(semaine, part_invisible, n=600, seed=100):
    """Dossiers de la semaine + vérité terrain (décision commission). Les cas « invisibles » ont un score bas."""
    rng = random.Random(seed + semaine)
    d = generer_dossiers(n, seed=seed + semaine)
    labels = []
    for x in d:
        s = calculer_score(x)
        labels.append(s >= 70)
    hauts = [i for i, l in enumerate(labels) if l]
    # une part des cas réellement à risque ne déclenche aucune règle (nouveau schéma)
    n_inv = int(round(part_invisible * len(hauts)))
    for i in rng.sample(range(n), n_inv * 3):               # on convertit des dossiers « propres » en cas invisibles
        if not labels[i] and calculer_score(d[i]) <= 40:
            labels[i] = True
            n_inv -= 1
            if n_inv <= 0:
                break
    return d, labels


def analyser(parts=(0.05, 0.05, 0.08, 0.12, 0.18, 0.25)):
    ref_d, _ = fenetre(0, 0.0)
    ref_scores = [calculer_score(x) for x in ref_d]
    out = []
    for w, part in enumerate(parts, start=1):
        d, labels = fenetre(w, part)
        scores = [calculer_score(x) for x in d]
        pred = [categoriser(s) == "Risque élevé" for s in scores]
        tp = sum(1 for p, l in zip(pred, labels) if p and l)
        fn = sum(1 for p, l in zip(pred, labels) if not p and l)
        rappel = tp / (tp + fn) if tp + fn else 1.0
        p = psi(ref_scores, scores)
        out.append({"semaine": w, "part_cas_invisibles": part, "psi_scores": round(p, 4), "rappel_pct": round(100 * rappel, 1),
                    "alerte_psi": p > SEUIL_PSI, "alerte_rappel": rappel < SEUIL_RAPPEL})
    return out
