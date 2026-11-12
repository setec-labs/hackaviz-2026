# Instructions pour les agents du service routing

## Responsabilite et architecture

Ce service expose un catalogue de scenarios de trajets et prepare leurs reports.
Il ne calcule pas encore de nouveaux itineraires ni les metriques des reports.

- Lire le [README](README.md) pour les contrats, le stockage et les codes HTTP.
- Les contrats publics sont dans
  [hackaviz_2026.routing](../../src/hackaviz_2026/routing.py).
  Reutiliser `Position` et `NormalizedScore` du package commun, sans les dupliquer.
- `src/routing/main.py` contient les routes, les dependances et la traduction
  des erreurs en reponses HTTP.
- `src/routing/repository.py` lit et valide les fichiers de scenarios.
- `src/routing/service.py` orchestre le catalogue et le `ReportProvider`.
- `src/routing/providers.py` prepare le calcul du report.
- Ne pas importer le service safety directement : reutiliser les contrats
  partages, puis definir explicitement son integration si elle devient necessaire.

Les routes declarent leurs modeles Pydantic de requete et de reponse. Elles ne
lisent pas les fichiers et ne manipulent pas directement les donnees des providers.
Les lectures de fichiers sont synchrones : les routes de catalogue sont des
fonctions `def`, executees hors de la boucle evenementielle par FastAPI.

## Ajouter ou modifier un scenario

1. Un scenario = **un fichier `journeys.json`** produit par le pipeline
   (`transit_accessibility.py` / `run_scenarios.py`) : une origine, une heure de
   depart et **plusieurs trajets** (`journeys`). Ne pas modifier le pipeline
   depuis l'API : c'est la responsabilite de son auteur.
2. Emplacement : `data/output/scenarios/<scenario_id>/journeys.json` (versionne),
   ou le dossier configure par `ROUTING_SCENARIOS_DIR`. Le chemin par defaut est
   relatif au repertoire de lancement : executer les commandes depuis la racine.
3. L'identifiant est le **nom du dossier** et doit respecter `ScenarioId`
   (majuscules autorisees, ex. `AccorHotel-Arena`). Garder cette validation sur
   toute route utilisant un identifiant de fichier.
4. Le fichier est valide par `ScenarioDocument.model_validate_json` (trajets non
   vides, `journey_id` uniques, aucun trajet avant `departure_time`). Ne pas
   contourner les validations avec `model_construct`.
5. `name` et `description` sont optionnels dans le fichier tant que le pipeline
   ne les exporte pas. Le repli (`describe_scenario`) derive le nom de l'identifiant
   et une description factuelle (depart, nombre de trajets et de destinations),
   met `metadata_generated=True` et journalise un avertissement. Ne jamais
   inventer de contenu (lieu, public, motif) absent des donnees.
6. Le modele `Journey` de l'API est plus strict que celui du pipeline
   (`extra="forbid"`, arrets non vides) : si une nouvelle sortie est rejetee,
   corriger la donnee ou faire evoluer le contrat explicitement, jamais en
   ignorant le fichier.

Le repository garde en cache, invalides par `(mtime_ns, size)`, les resumes de
tous les scenarios et les 2 derniers scenarios complets (LRU, ~150 Mo de JSON
chacun) : ne pas ajouter d'autre cache sans invalidation. `list_scenarios` lit
seulement l'en-tete (`ScenarioDocumentHeader`, JSON partiel sur 64 Ko) et compte
les `journey_id` ; il retombe sur une lecture complete si l'en-tete est
incomplet ou si les metadonnees doivent etre generees. Ne pas revenir a une
validation complete pour la liste (~30 s sur les donnees reelles). `get_routing_service` est
memoise par `lru_cache` : appeler `get_routing_service.cache_clear()` dans les
tests qui modifient `ROUTING_SCENARIOS_DIR`.

L'ancien format `data/routing/scenarios/<id>.json` (un trajet par scenario) est
abandonne.

Un dossier existant mais vide est un catalogue vide. Un dossier manquant, une
configuration vide, un nom de dossier invalide ou un fichier invalide est une
erreur `503`, jamais un catalogue vide ou partiel. Les erreurs de lecture sont
journalisees avec le chemin du fichier, sans exposer son contenu dans la
reponse HTTP.

## Invariants des trajets

- Coordonnees WGS84 ; les tableaux sont en ordre **longitude, latitude**.
- Les objets `Position` utilisent les champs nommes `latitude` et `longitude`.
- Les horaires portent un fuseau ; les etapes couvrent la duree du trajet sans
  trou ni chevauchement.
- `point_range` est un intervalle **semi-ouvert [debut, fin)**. Les etapes
  partitionnent toutes les coordonnees, sans trou ni chevauchement.
- `offsets_s` est relatif a `journey.start_time`, commence a zero, ne decroit pas
  et contient exactement une valeur par coordonnee.
- Les offsets de l'exemple sont arrondis : ne pas imposer une egalite exacte
  entre le dernier offset et la duree issue des horaires.
- Ne pas convertir silencieusement les geometries, changer l'ordre des axes ou
  perdre les etapes/identifiants GTFS lors d'un import.

## Implementer le report

`POST /report` recoit `{"scenario_id": ...}` et lit le scenario dans le catalogue
(`404` s'il est absent). Le report contient un `JourneyReport` **par trajet** ;
la position reportee est la derniere coordonnee du trajet, pas l'origine.
`destination.population` (optionnelle, exportee par le pipeline) est une piste
pour les effectifs, mais son usage reste a valider.

`UnimplementedReportProvider` leve actuellement `NotImplementedError`, traduit
en `501` par le service et la couche HTTP. Ne retourner aucune metrique fictive,
aucun zero par defaut et aucun resultat partiel.

Avant de remplacer ce provider :

1. Faire preciser les sources des effectifs, leur reference temporelle et la
   definition de la presence au point final (perimetre, fenetre temporelle).
2. Faire definir et documenter la methode de calcul du score.
3. Respecter `ReportProvider` et retourner un `ReportResponse` valide : pour
   chaque `JourneyReport`, `person_count` entier >= 0, `anxiety_index` fini dans [0, 1].
4. Malgre son nom, `anxiety_index` suit la convention commune :
   **0 = le moins favorable, 1 = le plus favorable**. Une mesure brute d'anxiete
   orientee dans l'autre sens doit etre transformee avant exposition.
5. Definir explicitement le comportement et le code HTTP si les donnees sont
   absentes. Une absence n'est pas equivalente a un effectif nul.
6. Injecter le provider dans `get_routing_service`, sans ajouter de calcul dans
   les routes, et tester le resultat au point final reel.

Un indicateur defavorable ne constitue jamais une preuve objective de danger.

## Validation et integration

```text
uv run --package routing python -m unittest discover -s services\routing\tests -v
uv run --package routing uvicorn routing.main:app --port 8001 --reload
```

Les tests utilisent des scenarios synthetiques et des dossiers temporaires :
ne pas les faire dependre du dossier local `data/` ou d'un fichier Downloads.
Seule exception : `tests/test_local_data.py` valide les sorties du pipeline dans
`data/output/scenarios/` lorsqu'elles existent et est ignore sinon. Le relancer
apres toute nouvelle execution du pipeline.
Tester les cas nominaux, donnees absentes/invalides, bornes, chronologie,
geometrie, erreurs de stockage et report non implemente.
Surcharger `get_routing_service` via `app.dependency_overrides` pour les tests API.

Les modeles d'erreurs HTTP sont partages dans
[hackaviz_2026.api](../../src/hackaviz_2026/api.py). Si ces contrats changent,
executer aussi les tests safety.
Verifier le demarrage reel du service apres une modification de code.

Le frontend consomme `GET /scenarios` (points de depart cliquables, infobulle
nom/description) et `GET /scenarios/{id}` (trajets). Toute modification de
`ScenarioSummary`, `Scenario` ou `Journey` doit etre repercutee dans
`frontend/src/api/` (types, validation, conversion) et ses tests.
Le CORS est configure par `ROUTING_CORS_ORIGINS`.
