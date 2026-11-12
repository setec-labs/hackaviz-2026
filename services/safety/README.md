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
uv run --package safety uvicorn safety.main:app --port 8002 --reload
```

Le port 8002 est celui attendu par le frontend. Le script `scripts/run_services.py`
à la racine lance tous les services. La documentation interactive est disponible
sur `http://localhost:8002/docs`.

Variables d'environnement :

- `SAFETY_LIGHTING_RASTER` : chemin du raster d'éclairage (par défaut
  `src/safety/luminosite.tif`) ;
- `SAFETY_CORS_ORIGINS` : origines autorisées, séparées par des virgules (par
  défaut `http://localhost:5173,http://127.0.0.1:5173`, le serveur Vite).

## API des indicateurs

- `GET /indicators` retourne les métadonnées des indicateurs disponibles.
- `POST /evaluate` reçoit `{"position": {"latitude": 48.8566, "longitude": 2.3522}}`
  et retourne la position et les résultats de tous les indicateurs.
- `POST /score` reçoit une position et une liste `weights` contenant des objets
  `{"indicator_id": "lighting", "weight": 1.0}`. Il retourne la position,
  les résultats des indicateurs demandés et leur moyenne pondérée.
- `POST /safety-index` reçoit `{"points": [{"latitude": ..., "longitude": ...}, ...]}`
  (5 000 points au plus) et retourne `{"indices": [{"latitude": ..., "longitude": ..., "value": ...}]}`
  dans l'ordre des points. `value` est la moyenne à poids égaux de tous les
  indicateurs, ou `null` si une donnée manque à cette position. C'est la route
  utilisée par le frontend.

Tous les résultats et le score global sont compris entre 0 et 1 : 0 représente
la situation la moins favorable et 1 la plus favorable. Ces indicateurs ne
constituent pas une preuve objective de danger. Les coordonnées sont exprimées
en WGS84 (EPSG:4326).

Les poids doivent être finis et positifs ou nuls ; au moins un doit être
strictement positif. Les identifiants doivent être uniques et connus. Un
indicateur associé à un poids nul est tout de même évalué et inclus dans la
réponse.

Codes d'erreur : 422 pour une entrée invalide, 400 pour un identifiant inconnu,
404 si aucune donnée ne couvre la position (`/evaluate` et `/score`), 501 pour un
indicateur non implémenté et 503 si la donnée source est absente ou illisible.

## Indicateur `lighting`

Source : `src/safety/luminosite.tif`, livré sur la branche `victoria`
(Lambert 93 / EPSG:2154, maille de 130 m, valeurs brutes de 0 à 100 dont
l'unité n'est pas documentée).

Calcul : position WGS84 → reprojection dans le CRS du raster (pyproj) → pixel
contenant la position → valeur brute (rasterio) → score linéaire `valeur / 100`.

La distribution est très concentrée vers 0 (médiane 0, 95 % des pixels sous
2,7) : avec cette normalisation linéaire, la plupart des lieux obtiennent un
score faible (Châtelet ≈ 0,20, Gare du Nord ≈ 0,17, bois de Vincennes ≈ 0,001).
Une position hors du raster ou sans donnée (nodata) n'a pas de score. Une valeur
brute hors de [0, 100] est traitée comme une donnée invalide (503).

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