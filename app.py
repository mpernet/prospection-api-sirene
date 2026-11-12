"""Application de prospection : définissez votre client idéal et extrayez les entreprises
correspondantes depuis l'API Sirene de l'INSEE.

Lancement : streamlit run app.py
"""

from __future__ import annotations

import io
import os

import pandas as pd
import requests
import streamlit as st

from constants import EXEMPLES_NAF, SECTIONS_NAF, TRANCHES_EFFECTIFS
from sirene_client import SireneClient, SireneError, echapper_valeur

st.set_page_config(page_title="Prospection Sirene", page_icon="🎯", layout="wide")


def construire_requete(
    codes_naf: list[str],
    prefixe_naf: bool,
    type_geo: str | None,
    valeurs_geo: list[str],
    tranches: list[str],
    actifs_seulement: bool,
    date_creation_min: str | None,
    denomination: str,
) -> str:
    conditions: list[str] = []
    if codes_naf:
        champ = "activitePrincipaleUniteLegale"
        codes = [echapper_valeur(c) for c in codes_naf]
        if prefixe_naf:
            conditions.append(f"{champ}:({' OR '.join(c + '*' for c in codes)})")
        else:
            conditions.append(f"{champ}:({' OR '.join(codes)})")
    if type_geo and valeurs_geo:
        champ_geo = {
            "Code postal": "codePostalEtablissement",
            "Code commune (INSEE)": "codeCommuneEtablissement",
        }[type_geo]
        conditions.append(f"{champ_geo}:({' OR '.join(valeurs_geo)})")
    if tranches:
        conditions.append(f"trancheEffectifsUniteLegale:({' OR '.join(tranches)})")
    if actifs_seulement:
        conditions.append("etatAdministratifUniteLegale:A")
    if date_creation_min:
        conditions.append(f"dateCreationUniteLegale:[{date_creation_min} TO *]")
    if denomination:
        conditions.append(f'denominationUniteLegale:"{denomination}"*')
    return " AND ".join(conditions)


def vers_excel(df: pd.DataFrame) -> bytes:
    tampon = io.BytesIO()
    with pd.ExcelWriter(tampon, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Entreprises")
    return tampon.getvalue()


st.title("🎯 Prospection Sirene — définissez votre client idéal")
st.caption(
    "Recherche d'entreprises et d'établissements sur le répertoire Sirene de l'INSEE "
    "(API Sirene 3.11). Renseignez vos critères, lancez la recherche, exportez vos leads."
)

cle_api = os.environ.get("INSEE_API_KEY", "")
try:
    cle_api = st.secrets.get("INSEE_API_KEY", cle_api)
except Exception:
    pass
cle_saisie = st.text_input(
    "Clé API INSEE",
    value=cle_api,
    type="password",
    help="Obtenue sur https://portail-api.insee.fr/ — stockée uniquement en mémoire.",
)
cle_api = cle_saisie or cle_api

with st.sidebar:
    st.header("👤 Votre client idéal")

    st.subheader("Secteur d'activité")
    section = st.selectbox(
        "Grande section NAF (optionnel)",
        ["—"] + [f"{c} — {l}" for c, l in SECTIONS_NAF.items()],
    )
    naf_saisi = st.text_input(
        "Codes NAF précis (séparés par des virgules)",
        placeholder="ex. 62.01Z, 62.02A",
    )
    prefixe_naf = st.checkbox(
        "Inclure les sous-codes (recherche par préfixe)",
        value=False,
        help="Ex. 62 → inclut 62.01Z, 62.02A, etc.",
    )
    with st.expander("Exemples de codes NAF"):
        st.write(pd.DataFrame(list(EXEMPLES_NAF.items()), columns=["Code", "Libellé"]))

    st.subheader("Zone géographique")
    type_geo = st.selectbox(
        "Type de zone",
        ["Aucune", "Code postal", "Code commune (INSEE)"],
    )
    geo_saisi = st.text_input(
        "Valeurs (séparées par des virgules)",
        placeholder="ex. 75011, 75012 ou 69123, 38185",
    )

    st.subheader("Taille (effectif salarié)")
    tranches_labels = {f"{c} — {l}": c for c, l in TRANCHES_EFFECTIFS.items()}
    tranches_choisies = st.multiselect(
        "Tranches d'effectif",
        list(tranches_labels),
        default=[],
    )

    st.subheader("Filtres complémentaires")
    actifs_seulement = st.checkbox("Uniquement les établissements actifs", value=True)
    date_creation_min = st.text_input(
        "Créé après (AAAA-MM-JJ, optionnel)",
        placeholder="ex. 2020-01-01",
    )
    denomination = st.text_input(
        "Dénomination contient (optionnel)",
        placeholder="ex. boulangerie",
    )

    max_resultats = st.number_input(
        "Nombre maximum d'entreprises à extraire",
        min_value=10,
        max_value=20000,
        value=1000,
        step=100,
    )

codes_naf = [c.strip().upper() for c in naf_saisi.replace(" ", "").split(",") if c.strip()]
if section != "—" and not codes_naf:
    codes_naf = [section.split(" — ")[0]]
valeurs_geo = [v.strip() for v in geo_saisi.replace(" ", "").split(",") if v.strip()]
tranches = [tranches_labels[t] for t in tranches_choisies]
type_geo_effectif = None if type_geo == "Aucune" else type_geo

requete = construire_requete(
    codes_naf,
    prefixe_naf,
    type_geo_effectif,
    valeurs_geo,
    tranches,
    actifs_seulement,
    date_creation_min or None,
    denomination.strip(),
)

st.subheader("🔍 Requête générée")
st.code(requete or "(aucun critère — la recherche est vide)", language="text")

lancer = st.button("🚀 Lancer la recherche", type="primary", disabled=not requete or not cle_api)
if not cle_api and requete:
    st.warning("Renseignez votre clé API INSEE dans le champ ci-dessus.")

if lancer:
    try:
        client = SireneClient(cle_api)
        with st.status("Recherche en cours…", expanded=True) as statut:
            total = client.total_resultats(requete)
            st.write(f"**{total}** établissements correspondent à vos critères.")
            st.write("Extraction en cours (limitée au quota de 30 requêtes/minute)…")
            lignes: list[dict] = []
            for lot in client.iterer_resultats(requete, int(max_resultats)):
                lignes.extend(lot)
                statut.update(label=f"{len(lignes)} / {min(total, max_resultats)} extraits…")
        st.session_state["resultats"] = pd.DataFrame(lignes)
        st.session_state["total"] = total
    except SireneError as erreur:
        st.error(str(erreur))
    except requests.RequestException as erreur:
        st.error(f"Erreur réseau : {erreur}")

resultats: pd.DataFrame | None = st.session_state.get("resultats")
if resultats is not None:
    total = st.session_state.get("total", len(resultats))
    st.subheader("📊 Résultats")
    c1, c2, c3 = st.columns(3)
    c1.metric("Établissements correspondants", total)
    c2.metric("Extraits", len(resultats))
    siege = (resultats["Siège"] == "Oui").sum() if not resultats.empty else 0
    c3.metric("Dont sièges sociaux", int(siege))

    if resultats.empty:
        st.info("Aucun résultat. Élargissez vos critères.")
    else:
        affichage = resultats.copy()
        affichage["Effectifs (entreprise)"] = (
            affichage["Tranche effectifs (entreprise)"].map(TRANCHES_EFFECTIFS).fillna(affichage["Tranche effectifs (entreprise)"])
        )
        st.dataframe(affichage, use_container_width=True, height=480)
        colonnes_export = [c for c in affichage.columns if c != "Effectifs (entreprise)"]

        d1, d2 = st.columns(2)
        d1.download_button(
            "⬇️ Exporter en CSV",
            resultats[colonnes_export].to_csv(index=False).encode("utf-8-sig"),
            file_name="prospection_sirene.csv",
            mime="text/csv",
        )
        d2.download_button(
            "⬇️ Exporter en Excel",
            vers_excel(resultats[colonnes_export]),
            file_name="prospection_sirene.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        st.subheader("Répartition par secteur")
        repartition = resultats.groupby("Code NAF").size().reset_index(name="Nombre")
        st.bar_chart(repartition, x="Code NAF", y="Nombre")
