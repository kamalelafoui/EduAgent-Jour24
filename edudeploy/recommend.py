"""Aide au choix du mode de déploiement (tableau « Quand l'utiliser ? » du cours)."""
OUTILS = {"batch": "Apache Airflow, Dagster, Prefect", "real-time": "API REST (FastAPI) conteneurisée",
          "streaming": "Apache Kafka, Apache Flink, AWS Kinesis", "edge": "TensorFlow Lite, Core ML, ONNX"}


def recommander(latence_tolerance_ms, volume_par_jour, flux_continu=False, connectivite="stable", donnees="normales"):
    if connectivite == "aucune" or donnees == "maximale":
        mode, why = "edge", "pas de réseau fiable ou confidentialité maximale : exécution sur l'appareil"
    elif latence_tolerance_ms >= 3_600_000:
        mode, why = "batch", "résultat tolérable à l'heure : traitement planifié de gros volumes"
    elif flux_continu and volume_par_jour >= 100_000:
        mode, why = "streaming", "flux continu et fort volume : traitement dès l'arrivée des événements"
    else:
        mode, why = "real-time", "réponse immédiate à une requête utilisateur"
    return {"mode": mode, "justification": why, "outils_cles": OUTILS[mode]}
