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

Si le service utilise FastAPI et Uvicorn, la commande prendra par exemple la forme :

```powershell
uv run --package routing uvicorn routing.main:app --reload
```

Adaptez le chemin du module à la structure réelle du service.

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
    "origin_lat": 48.853563,
    "origin_lon": 2.372961,
    "departure_time": "02:00:00"
  },
  {
    "scenario_id": "scenario-02",
    "origin_lat": 48.856600,
    "origin_lon": 2.352200,
    "departure_time": "06:30:00"
  }
]
```

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