# Routing Service

Cette brique est responsable des fonctionnalités liées aux trajets et aux temps de parcours.

Elle expose les traitements nécessaires aux autres composants du projet, notamment au frontend.

## Installation

Depuis la racine du repository :

```powershell
uv sync
```

`uv` installe automatiquement les dépendances nécessaires au workspace.

## Ajouter une bibliothèque

Une dépendance spécifique au service Routing doit être ajoutée à ce projet :

```powershell
uv add --package routing <librairie>
```

Par exemple :

```powershell
uv add --package routing httpx
```

ou :

```powershell
uv add --package routing fastapi httpx
```

Évitez :

```powershell
pip install ...
```

La dépendance doit être déclarée afin que les autres participants puissent retrouver exactement le même environnement.

## Exécuter le service

Depuis la racine :

```powershell
uv run --package routing <commande>
```

```powershell
uv run --package routing uvicorn routing.main:app --port 8001 --reload
```

Les commandes sont à lancer depuis la racine du repository. La documentation
interactive est disponible sur `http://localhost:8001/docs`.

## Scénarios et stockage

Un scénario correspond à **un fichier `journeys.json` produit par le pipeline**
(voir plus bas) : une origine, une heure de départ et **plusieurs trajets**
vers différentes destinations.

L'API lit directement les sorties du pipeline, versionnées dans
`data/output/scenarios/<scenario_id>/journeys.json`. L'identifiant du scénario
est le **nom du dossier** (par exemple `AccorHotel-Arena`). Un autre
emplacement peut être défini avant le lancement :

```powershell
$env:ROUTING_SCENARIOS_DIR = "C:\chemin\vers\scenarios"
```

Les identifiants utilisent des lettres ASCII (majuscules autorisées), des
chiffres, des tirets ou des underscores, commencent par une lettre ou un
chiffre et font au plus 128 caractères. Un dossier sans `journeys.json` est
ignoré ; un dossier au nom invalide est une erreur. Le catalogue est trié par
nom de dossier. Chaque fichier n'est relu que si sa date de modification ou sa
taille change (cache en mémoire).

Les contrats Pydantic sont définis dans
[`src/hackaviz_2026/routing.py`](../../src/hackaviz_2026/routing.py) :

- `ScenarioDocument` : contenu d'un `journeys.json` (`name` et `description`
  optionnels, `origin`, `departure_time`, `journeys`) ;
- `ScenarioSummary` : `id`, `name`, `description`, `metadata_generated`,
  `origin`, `departure_time`, `journey_count` ;
- `Scenario` : ces métadonnées et la liste complète `journeys` ;
- `Journey` : `journey_id` (unique dans le scénario), `destination` (avec
  `population` optionnelle), `start_time`, `end_time`, `legs`, `coordinates`,
  `offsets_s` ;
- `JourneyLeg` : mode (`walk_access`, `walk_egress`, `walk_transfer`,
  `walk_direct`, `wait`, `transit`), horaires, arrêts, éventuel identifiant
  GTFS et `point_range`.

### Métadonnées générées (développement)

Les sorties actuelles du pipeline n'ont pas encore de `name` ni de
`description` à la racine. En leur absence, l'API dérive des métadonnées
**uniquement à partir des données** et le signale :

- `name` : identifiant du dossier, tirets et underscores remplacés par des espaces ;
- `description` : date et heure de départ, nombre de trajets et de destinations ;
- `metadata_generated: true` et un avertissement dans les logs.

Dès que le pipeline exporte ces champs, ils sont utilisés tels quels et
`metadata_generated` passe à `false`.

### Géométrie et temps

- `origin` et `destination` utilisent `latitude` / `longitude` en WGS84.
- Les éléments de `coordinates` sont dans l'ordre **`[longitude, latitude]`**.
- Les coordonnées sont bornées et les nombres doivent être finis.
- `offsets_s` contient un décalage en secondes depuis `journey.start_time` pour
  chaque coordonnée, commence à zéro et est croissant au sens large.
- Les horaires doivent porter un fuseau. Les étapes couvrent toute la durée du
  trajet sans trou ni chevauchement.
- Les intervalles `point_range` sont **semi-ouverts `[début, fin)`**, indexés à
  partir de zéro, et partitionnent les coordonnées dans l'ordre.
- Les décalages de l'exemple sont arrondis : leur dernière valeur n'est pas
  obligatoirement égale à la durée exacte calculée depuis les horaires.

## Routes

### `GET /scenarios`

Retourne `list[ScenarioSummary]` (origine et métadonnées, sans géométries).
Les fichiers complets sont néanmoins validés avant d'être listés.

### `GET /scenarios/{scenario_id}`

Retourne un `Scenario` complet, avec tous ses trajets et leurs géométries
(environ 2 à 3 Mo par scénario).

### `POST /report`

Reçoit un `ReportRequest` sous la forme `{"scenario_id": "<id>"}` : le
scénario est lu dans le catalogue (`404` s'il est absent).

Le futur `ReportResponse` contiendra `scenario_id` et, pour chaque trajet,
un `JourneyReport` :

- `journey_id` ;
- `position` : le point final réel, soit la dernière coordonnée du trajet ;
- `person_count` : un entier positif ou nul ;
- `anxiety_index` : un score normalisé dans `[0, 1]`.

Malgré son nom, `anxiety_index` suit la convention commune des scores du projet :
**0 = situation la moins favorable, 1 = la plus favorable**. Ce n'est pas une
mesure brute d'anxiété, ni une preuve objective de danger.

Le calcul des effectifs et du score **n'est pas implémenté**. La route retourne
actuellement **HTTP 501**, sans valeur fictive, zéro par défaut ni résultat
partiel. Les sources de fréquentation, leur référence temporelle et la méthode
de calcul du score restent à définir avant d'implémenter `ReportProvider`.

### Erreurs

- `422` : requête invalide ou identifiant de chemin invalide ;
- `404` : scénario demandé absent d'un dossier disponible ;
- `503` : dossier absent/inaccessible, fichier illisible ou invalide,
  configuration vide ou nom de dossier qui n'est pas un identifiant valide ;
- `501` : report non implémenté.

Un dossier existant et vide retourne `[]`. Un dossier absent ou un fichier
invalide ne sont jamais ignorés silencieusement : pas de catalogue partiel.

## Tests

```powershell
uv run --package routing python -m unittest discover -s services\routing\tests -v
```

Les tests utilisent des scénarios synthétiques, isolés dans des dossiers
temporaires. Seul `test_local_data.py` valide les sorties réelles du pipeline
présentes dans `data/output/scenarios/` ; il est ignoré si ce dossier n'existe pas.

## Intégration frontend

Le frontend (mode API) appelle `GET /scenarios` pour afficher les points de
départ cliquables, puis `GET /scenarios/{scenario_id}` pour charger les trajets
du scénario sélectionné. Les origines CORS autorisées sont configurables via
`ROUTING_CORS_ORIGINS` (par défaut `http://localhost:5173` et
`http://127.0.0.1:5173`).

## Calculer l'accessibilité en transports en commun

Le script `routing.transit_accessibility` reprend le calcul du notebook de
preuve de concept et exporte les itinéraires dans un document JSON.


```powershell
uv run --package routing transit-accessibility --data-dir ..\..\..\HAckaton\sources
```

Le résultat et les caches resteront dans `data/output/transit_accessibility/`.

Installez les dépendances du workspace, puis lancez le test avec les trois
destinations d'exemple :

```powershell
uv sync
uv run --package routing transit-accessibility
```

Pour calculer une destination à la mairie de chaque commune d'Île-de-France :

```powershell
uv run --package routing transit-accessibility --all-communes
```

Les coordonnées des mairies et les populations sont téléchargées depuis
`geo.api.gouv.fr`, puis mises en cache dans
`communes_idf_mairies_population_v2.json` dans le dossier de cache. Chaque
commune francilienne est une destination ; Paris est remplacée par ses 20
arrondissements municipaux, chacun avec son propre point de mairie et sa
population. Le champ `destination.population` du JSON exporté est un entier
(les trois destinations de démonstration ont `null`). Pour un essai limité,
combinez par exemple
`--all-communes --max-destinations 10`. La date, l'heure, l'origine,
les dossiers de données et de sortie peuvent être ajustés avec `--service-date`,
`--departure-time`, `--origin-lat`, `--origin-lon`, `--data-dir` et
`--output-dir`.

Par défaut, le JSON final et les caches piétons sont écrits sous
`data/output/transit_accessibility/`. Le script peut aussi être appelé depuis
n'importe quel répertoire : ses chemins par défaut sont calculés relativement
à la racine Git, et non au répertoire courant.

### Lancer plusieurs scénarios

Créez un fichier JSON (par exemple `data/scenarios.json`) contenant un objet
par origine et heure de départ :

```json
[
  {
    "scenario_id": "scenario-01",
    "description": "Départ de la rue de Lappe à 2 h du matin.",
    "origin_lat": 48.853563,
    "origin_lon": 2.372961,
    "departure_time": "02:00:00"
  },
  {
    "scenario_id": "scenario-02",
    "description": "Départ de la gare de Lyon à 6 h 30.",
    "origin_lat": 48.856600,
    "origin_lon": 2.352200,
    "departure_time": "06:30:00"
  }
]
```

Le champ `description` est obligatoire et doit être une chaîne. L’identifiant
`scenario_id` est écrit dans le JSON de sortie comme `name`, et `description`
est également recopiée à la racine du document.

Ajoutez les huit autres objets pour vos dix scénarios, puis lancez depuis la
racine du dépôt :

```powershell
uv run --package routing transit-accessibility-scenarios `
  --scenarios data\scenarios.json `
  --data-dir ..\..\..\HAckaton\sources `
  --all-communes
```

Le lanceur exécute les scénarios **séquentiellement** pour éviter de multiplier
la consommation mémoire. Chaque résultat est écrit séparément sous
`data/output/scenarios/<scenario_id>/journeys.json`. Le cache du graphe OSM
et celui des mairies sont partagés dans
`data/output/transit_accessibility_cache/` : le graphe est construit au premier
lancement, puis réutilisé automatiquement. En cas d'interruption, ajoutez
`--resume` pour ignorer les scénarios dont le JSON de sortie est déjà valide.
Vous pouvez valider le pipeline sur une liste réduite avec
`--max-destinations 10`.

Le cache évite de reconstruire le graphe, mais le calcul CSA et les sorties
piétonnes restent à effectuer pour chaque origine/heure. À environ 30 minutes
par scénario, dix scénarios prendront encore près de cinq heures de calcul.
Pour réduire davantage le temps total, il faudrait optimiser ou profiler ces
étapes coûteuses ; lancer plusieurs calculs simultanément n'est pas activé par
défaut car chaque processus charge un graphe volumineux en mémoire.

## Interfaces communes

Si ce service échange des objets avec le frontend ou d'autres services, utilisez autant que possible les modèles Pydantic communs situés dans :

```text
src/hackaviz_2026/
```

Cela évite de définir plusieurs fois des structures légèrement différentes pour représenter les mêmes données.

## Contribution

Travaillez sur votre branche personnelle.

Lorsque votre modification fonctionne :

1. committez ;
2. poussez votre branche ;
3. créez une Pull Request vers `develop`.

Consultez le `CONTRIBUTING.md` situé à la racine pour le workflow complet.