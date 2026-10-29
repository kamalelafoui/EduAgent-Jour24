"""Exécute la simulation complète et produit outputs/results.json + graphiques."""
import json
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from edudeploy import drift, modes
from edudeploy.recommend import recommander

N = 2000
dos = modes.generer_dossiers(N)
cmp_ = modes.comparer(dos)
reel = modes.comparer(modes.charger_csv("data/dossiers.csv"))
dr = drift.analyser()
SC = [("Consultation du statut par les candidats sur le portail", (1000, 3000, False, "stable", "normales"), "real-time"),
      ("Classement nocturne de 5 000 dossiers", (8 * 3600 * 1000, 5000, False, "stable", "normales"), "batch"),
      ("Pic de dépôts à la clôture des candidatures", (500, 500_000, True, "stable", "normales"), "streaming"),
      ("Jury sur tablette, centre d'examen sans réseau", (1000, 200, False, "aucune", "normales"), "edge"),
      ("Dossiers confidentiels (handicap, dérogations) traités localement", (1000, 300, False, "stable", "maximale"), "edge")]
scen = []
for nom, a, att in SC:
    r = recommander(*a); assert r["mode"] == att, (nom, r)
    scen.append({"scenario": nom, "mode": r["mode"], "justification": r["justification"], "outils_cles": r["outils_cles"]})
json.dump({"n_simulation": N, "params": modes.PARAMS, "modes": cmp_, "csv_reel_14": reel, "derive": dr, "scenarios": scen},
          open("outputs/results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

NAVY, YEL, GR, RD = "#0B3C5D", "#FDB913", "#1E8E4E", "#C62828"
ms = ["real-time", "batch", "streaming", "edge"]; cols = [NAVY, "#7FB6DD", "#2E9E5B", YEL]
fig, ax = plt.subplots(1, 3, figsize=(15, 4.4))
d = [cmp_[m]["resume"]["delai_resultat_moyen_s"] for m in ms]
b = ax[0].bar(ms, d, color=cols); ax[0].set_yscale("log"); ax[0].set_title("Délai moyen avant résultat (s, échelle log)", color=NAVY, weight="bold")
for r, v in zip(b, d): ax[0].text(r.get_x() + r.get_width() / 2, v * 1.15, f"{v:,.3f}".rstrip("0").rstrip(".") if v < 100 else f"{v/3600:.1f} h", ha="center", fontsize=9)
c = [cmp_[m]["resume"]["cout_1000_dossiers_usd"] for m in ms]
b = ax[1].bar(ms, c, color=cols); ax[1].set_title("Coût pour 1 000 dossiers (USD, simulé)", color=NAVY, weight="bold")
for r, v in zip(b, c): ax[1].text(r.get_x() + r.get_width() / 2, v + 0.002, f"{v:.4f}", ha="center", fontsize=9)
w = [x["semaine"] for x in dr]
ax[2].plot(w, [x["rappel_pct"] for x in dr], "o-", color=RD, lw=2.5, label="Rappel « risque élevé » (%)")
ax[2].axhline(85, color=GR, ls="--", label="Seuil d'alerte 85 %"); ax[2].set_ylim(70, 100)
ax[2].set_title("Dérive de performance (simulée)", color=NAVY, weight="bold"); ax[2].set_xlabel("Semaine"); ax[2].legend(loc="lower left", fontsize=8)
for a in ax: a.spines[["top", "right"]].set_visible(False)
plt.tight_layout(); plt.savefig("outputs/comparaison_modes.png", dpi=150, facecolor="white")
print("ok", {m: cmp_[m]["resume"]["latence_traitement_p95_ms"] for m in ms})
