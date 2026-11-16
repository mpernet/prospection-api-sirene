# Prospection Sirene 🎯

Application Streamlit pour définir votre **client idéal** (secteur NAF, zone géographique,
taille d'effectif, état actif, date de création…) et **extraire la liste des entreprises
correspondantes** depuis le répertoire Sirene de l'INSEE (API Sirene 3.11), avec export
**CSV** et **Excel**.

## 1. Obtenir une clé API

1. Créez un compte sur le portail développeur de l'INSEE : <https://portail-api.insee.fr/>
2. Abonnez-vous au produit **API Sirene** (gratuit).
3. Copiez votre clé (elle est passée dans l'en-tête `X-INSEE-Api-Key-Integration`).

Quota en environnement d'intégration : **30 requêtes/minute** — l'application respecte
automatiquement cette limite (l'extraction de 1 000 résultats prend environ 1 minute).

## 2. Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Configuration de la clé

Deux options (la clé n'est jamais stockée dans le code) :

- **Variable d'environnement** :
  ```bash
  export INSEE_API_KEY="votre-cle"     # Windows : set INSEE_API_KEY=votre-cle
  ```
- **Ou saisie dans l'application** : champ masqué au lancement (ou fichier `.streamlit/secrets.toml`
  contenant `INSEE_API_KEY = "votre-cle"`).

⚠️ Ne partagez jamais votre clé et ne la commitez pas (le `.gitignore` exclut `.env`,
`.streamlit/secrets.toml` et les exports).

## 4. Lancement

```bash
streamlit run app.py
```

L'interface s'ouvre sur <http://localhost:8501>.

## 5. Utilisation

1. Dans la barre latérale, décrivez votre client idéal :
   - **Secteur** : grande section NAF (A à U) et/ou codes NAF précis (avec option « sous-codes ») ;
   - **Zone** : un ou plusieurs départements (liste complète avec leurs noms), codes postaux ou codes communes INSEE ;
   - **Taille** : tranches d'effectif salarié (de « non employeur » à « 10 000 salariés et plus ») ;
   - **Filtres** : établissements actifs uniquement, création après une date, dénomination.
2. Vérifiez la **requête générée** (syntaxe officielle de l'API Sirene).
3. Cliquez sur **Lancer la recherche** : le nombre total d'établissements correspondants
   s'affiche, puis l'extraction paginée s'exécute.
4. Consultez le tableau, la répartition par secteur, puis **exportez** en CSV ou Excel.

## Structure du projet

```
app.py            Interface Streamlit (critères, requête, résultats, exports)
sirene_client.py  Client API Sirene 3.11 (pagination, quota 30 req/min, gestion d'erreurs)
constants.py      Nomenclatures INSEE (tranches d'effectif, sections NAF, exemples de codes)
```

## Notes techniques

- Endpoint utilisé : `GET https://api.insee.fr/api-sirene/3.11/siret` (recherche par critères,
  1 000 résultats max par page, pagination automatique).
- Le filtre département utilise la syntaxe officielle de l'API : `codeCommuneEtablissement:69*`
  (les codes communes INSEE commencent toujours par le numéro de département, y compris
  2A/2B pour la Corse et 971–976 pour l'outre-mer).
- Les erreurs courantes sont explicitées dans l'interface : clé invalide (401),
  erreur de syntaxe de requête (400), quota atteint (429).
- Les données proviennent du répertoire Sirene géré par l'INSEE ; les tranches d'effectif
  sont actualisées une fois par an (validité au 31/12 de l'année n-2).
