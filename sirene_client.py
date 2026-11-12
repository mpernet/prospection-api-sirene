"""Client pour l'API Sirene 3.11 de l'INSEE (https://portail-api.insee.fr/)."""

from __future__ import annotations

import time
from typing import Any, Dict, Iterator, List, Optional

import requests

BASE_URL = "https://api.insee.fr/api-sirene/3.11/siret"
MAX_PAR_PAGE = 1000
REQUETES_PAR_MINUTE = 30
_PAUSE_S = 60.0 / REQUETES_PAR_MINUTE + 0.2


class SireneError(Exception):
    """Erreur renvoyée par l'API Sirene."""


def echapper_valeur(valeur: str) -> str:
    """Échappe les caractères spéciaux de la syntaxe (le point des codes NAF notamment)."""
    return valeur.replace(".", "\\.")


class SireneClient:
    def __init__(self, api_key: str):
        if not api_key:
            raise SireneError("Clé API INSEE manquante.")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-INSEE-Api-Key-Integration": api_key,
                "Accept": "application/json",
            }
        )
        self._dernier_appel = 0.0

    def _respecter_limite(self) -> None:
        attente = _PAUSE_S - (time.monotonic() - self._dernier_appel)
        if attente > 0:
            time.sleep(attente)
        self._dernier_appel = time.monotonic()

    def _get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self._respecter_limite()
        reponse = self.session.get(BASE_URL, params=params, timeout=60)
        if reponse.status_code == 401:
            raise SireneError("Clé API invalide ou expirée (401). Vérifiez votre token INSEE.")
        if reponse.status_code == 429:
            raise SireneError("Quota de requêtes atteint (429). Attendez un instant avant de relancer.")
        if reponse.status_code >= 400:
            try:
                message = reponse.json().get("header", {}).get("message", reponse.text[:300])
            except ValueError:
                message = reponse.text[:300]
            raise SireneError(f"Erreur {reponse.status_code} de l'API Sirene : {message}")
        return reponse.json()

    def total_resultats(self, q: str) -> int:
        donnees = self._get({"q": q, "nombre": 1, "debut": 0})
        return int(donnees.get("header", {}).get("total", 0))

    def iterer_resultats(self, q: str, max_resultats: int, par_page: int = 500) -> Iterator[List[Dict[str, Any]]]:
        """Itère sur les pages de résultats, par lots d'établissements."""
        par_page = min(par_page, MAX_PAR_PAGE)
        debut = 0
        while debut < max_resultats:
            donnees = self._get({"q": q, "nombre": par_page, "debut": debut})
            etablissements = donnees.get("etablissements", [])
            if not etablissements:
                break
            lot = [extraire_etablissement(e) for e in etablissements]
            lot = [e for e in lot if e is not None]
            yield lot
            total = int(donnees.get("header", {}).get("total", 0))
            debut += par_page
            if debut >= total:
                break


def extraire_etablissement(brut: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Aplatit un établissement (structure plate de l'API 3.11) en enregistrement simple."""
    if not brut.get("siret"):
        return None
    unite = brut.get("uniteLegale") or {}
    adresse = brut.get("adresseEtablissement") or {}

    def champ(nom: str) -> str:
        valeur = brut.get(nom) or unite.get(nom) or adresse.get(nom) or ""
        return str(valeur).strip()

    etat = champ("etatAdministratifEtablissement") or champ("etatAdministratifUniteLegale")
    naf = champ("activitePrincipaleUniteLegale")
    return {
        "SIREN": champ("siren"),
        "SIRET": champ("siret"),
        "Dénomination": champ("denominationUniteLegale"),
        "Enseigne": champ("denominationUsuelle1UniteLegale"),
        "Siège": "Oui" if brut.get("etablissementSiege") else "Non",
        "État": "Actif" if etat == "A" else "Fermé",
        "Code NAF": naf,
        "Tranche effectifs (établissement)": champ("trancheEffectifsEtablissement"),
        "Tranche effectifs (entreprise)": champ("trancheEffectifsUniteLegale"),
        "Catégorie d'entreprise": champ("categorieEntreprise"),
        "ESS": "Oui" if champ("economieSocialeSolidaireUniteLegale") == "true" else "Non",
        "Date de création (entreprise)": champ("dateCreationUniteLegale"),
        "Complément d'adresse": champ("complementAdresseEtablissement"),
        "Numéro de voie": champ("numeroVoieEtablissement"),
        "Indice de répétition": champ("indiceRepetitionEtablissement"),
        "Type de voie": champ("typeVoieEtablissement"),
        "Voie": champ("libelleVoieEtablissement"),
        "Code postal": champ("codePostalEtablissement"),
        "Commune": champ("libelleCommuneEtablissement"),
    }
