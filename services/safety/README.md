# Safety Service

Cette brique analyse les données et indicateurs susceptibles d'influencer le sentiment de sécurité lors d'un trajet.

Elle peut notamment exploiter des informations relatives à l'environnement du trajet, comme l'éclairage ou certaines caractéristiques des arrêts et espaces traversés.

> L'objectif n'est pas de déterminer qu'un lieu est objectivement « dangereux », mais de construire et visualiser des indicateurs pouvant contribuer au sentiment de sécurité ou d'insécurité.

## Installation

Depuis la racine du repository :

```powershell
uv sync
```

## Ajouter une bibliothèque

Pour ajouter une dépendance spécifique à ce service :

```powershell
uv add --package safety <librairie>
```

Par exemple :

```powershell
uv add --package safety geopandas
```

ou :

```powershell
uv add --package safety geopandas shapely pandas
```

Évitez d'utiliser :

```powershell
pip install ...
```

L'ajout via `uv` permet de déclarer la dépendance dans le projet et de conserver un environnement reproductible pour toute l'équipe.

## Exécuter le service

Depuis la racine :

```powershell
uv run --package safety <commande>
```

```powershell
uv run --package safety uvicorn safety.main:app --reload
```

La documentation interactive est disponible sur `http://localhost:8000/docs`.

## API des indicateurs

- `GET /indicators` retourne les métadonnées des indicateurs disponibles.
- `POST /evaluate` reçoit `{"position": {"latitude": 48.8566, "longitude": 2.3522}}`
  et retourne la position et les résultats de tous les indicateurs.
- `POST /score` reçoit une position et une liste `weights` contenant des objets
  `{"indicator_id": "lighting", "weight": 1.0}`. Il retourne la position,
  les résultats des indicateurs demandés et leur moyenne pondérée.

Tous les résultats et le score global sont compris entre 0 et 1 : 0 représente
la situation la moins favorable et 1 la plus favorable. Ces indicateurs ne
constituent pas une preuve objective de danger. Les coordonnées sont exprimées
en WGS84 (EPSG:4326).

Les poids doivent être finis et positifs ou nuls ; au moins un doit être
strictement positif. Les identifiants doivent être uniques et connus. Un
indicateur associé à un poids nul est tout de même évalué et inclus dans la
réponse. Les entrées invalides produisent une réponse HTTP 422 et les
identifiants inconnus une réponse HTTP 400.

L'indicateur `lighting` est déclaré mais pas encore implémenté : son évaluation
retourne une erreur HTTP 501, jamais une valeur fictive. Son implémentation
future devra transformer les coordonnées WGS84 vers le CRS du GeoTIFF si
nécessaire, localiser le pixel, lire sa valeur brute et appliquer une
normalisation propre à l'indicateur. La lecture raster, la transformation de
coordonnées et la stratégie de normalisation ne sont pas encore implémentées.

Cette API ne fournit pas encore la route batch `/safety-index` attendue par le
client frontend provisoire ; le frontend doit continuer à utiliser ses mocks
jusqu'à l'alignement des contrats.

## Tests

```powershell
uv run --package safety python -m unittest discover -s services\safety\tests -v
```

## Modèles de données communs

Les structures échangées avec les autres briques doivent autant que possible utiliser les modèles communs définis dans :

```text
src/hackaviz_2026/
```

Par exemple, un trajet, un point géographique ou un indicateur partagé ne devrait idéalement pas avoir trois définitions différentes dans trois services.

## Contribution

Travaillez sur votre branche personnelle puis créez une Pull Request vers `develop`.

Le workflow Git complet est décrit dans le `CONTRIBUTING.md` situé à la racine du repository.