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

Un scénario correspond à **un seul trajet**, avec un identifiant stable, un nom,
une description en français et un type extensible (`hospital`, `concert_hall`,
`train_station`, etc.). Le type n'est pas limité à une liste codée en dur.

Le format retenu est **un fichier JSON par scénario**, plutôt que JSONL :
il permet de modifier et valider un scénario indépendamment, et reprend la
structure des trajets de l'exemple `journeys.json`.

Par défaut, les fichiers sont lus dans `data/routing/scenarios/`, relativement
au répertoire de lancement. Ce dossier de données n'est pas versionné.
Un autre emplacement peut être défini avant le lancement :

```powershell
$env:ROUTING_SCENARIOS_DIR = "C:\chemin\vers\scenarios"
```

Le nom du fichier doit correspondre à son champ `id` : par exemple
`tour-eiffel.json` contient `"id": "tour-eiffel"`. Les identifiants utilisent
des lettres minuscules ASCII, des chiffres, des tirets ou des underscores,
commencent par une lettre ou un chiffre et font au plus 128 caractères.
Le catalogue est trié par nom de fichier et ne lit que les fichiers `.json`
directement présents dans le dossier, sans parcourir les sous-dossiers.
Les modifications sont visibles à la requête suivante, sans cache.

Les contrats Pydantic sont définis dans
[`src/hackaviz_2026/routing.py`](../../src/hackaviz_2026/routing.py) :

- `ScenarioSummary` : `id`, `name`, `description`, `type` ;
- `Scenario` : ces métadonnées, `origin`, `departure_time` et un unique `journey` ;
- `Journey` : `journey_id`, `destination`, `start_time`, `end_time`, `legs`,
  `coordinates`, `offsets_s` ;
- `JourneyLeg` : mode, horaires, arrêts, éventuel identifiant GTFS et `point_range`.

Le fichier fourni `journeys.json` contient plusieurs trajets sous `journeys` :
il faut donc créer un scénario par élément de cette liste, en conservant
`origin` et `departure_time` et en ajoutant les métadonnées du scénario.
Les noms et descriptions sont rédigés en français par l'auteur des données ;
aucune détection automatique de langue n'est effectuée.

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

Retourne `list[ScenarioSummary]`, sans charger les géométries dans la réponse.
Les fichiers complets sont néanmoins validés avant d'être listés.

### `GET /scenarios/{scenario_id}`

Retourne un `Scenario` complet, comprenant son trajet et sa géométrie.

### `POST /report`

Reçoit un `ReportRequest` sous la forme `{"scenario": <scénario complet>}`.
Le scénario est validé indépendamment du catalogue : il n'a pas besoin d'être
déjà enregistré dans un fichier.

Le futur `ReportResponse` contiendra :

- `scenario_id` ;
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
  configuration vide ou identifiant différent du nom du fichier ;
- `501` : report non implémenté.

Un dossier existant et vide retourne `[]`. Un dossier absent ou un fichier
invalide ne sont jamais ignorés silencieusement : pas de catalogue partiel.

## Tests

```powershell
uv run --package routing python -m unittest discover -s services\routing\tests -v
```

Les tests utilisent des scénarios synthétiques, isolés dans des dossiers
temporaires, et ne nécessitent pas le fichier téléchargé. Seul
`test_local_data.py` valide les scénarios présents dans
`data/routing/scenarios/` ; il est ignoré si ce dossier n'existe pas.

## Intégration frontend

Le frontend attend encore le contrat provisoire `GET /trips`. Cette route
n'est pas fournie par cette API de scénarios : l'adaptation du client frontend
reste à réaliser. Le mode mocks reste inchangé.

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