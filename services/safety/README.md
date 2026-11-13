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
  `src/safety/luminosite_log.tif`) ;
- `SAFETY_RIDERSHIP_CSV` : chemin des estimations par arc (par défaut
  `data/output/ridership/ridership_by_transit_arc.csv`, depuis la racine du dépôt) ;
- `SAFETY_CORS_ORIGINS` : origines autorisées, séparées par des virgules (par
  défaut `http://localhost:5173,http://127.0.0.1:5173`, le serveur Vite).

## API des indicateurs

- `GET /indicators` retourne les métadonnées des indicateurs disponibles.
- `POST /evaluate` reçoit `{"position": {"latitude": 48.8566, "longitude": 2.3522}}`
  et retourne les indicateurs de position (éclairage). La fréquentation requiert un arc.
- `POST /score` reçoit une position et une liste `weights` contenant des objets
  `{"indicator_id": "lighting", "weight": 1.0}`. Il retourne la position,
  les résultats des indicateurs demandés et leur moyenne pondérée.
- `POST /safety-index` reçoit `{"points": [{"latitude": ..., "longitude": ...}, ...]}`
  (5 000 points au plus) et retourne `{"indices": [{"latitude": ..., "longitude": ..., "value": ...}]}`
  dans l'ordre des points. `value` est la moyenne à poids égaux de tous les
  indicateurs, ou `null` si une donnée manque à cette position. C'est la route
  historique pour les seuls indicateurs de position ; elle reste compatible.
- `POST /journey-safety` est la route utilisée par le frontend. Elle reçoit
  `{"journeys": [...], "weights": {"lighting": 0.5, "ridership": 0.5}}`.
  Les trajets utilisent le modèle partagé `Journey` de routing, sans duplication.
  Un lot contient au plus 100 trajets et 5 000 coordonnées. Les poids sont dans
  `[0, 1]`, de somme 1 (tolérance numérique `1e-9`), avec 50/50 par défaut.
  La réponse contient `journeys` dans l'ordre demandé : `journey_id`, `values`
  (un indice local par coordonnée), `score` (global, ou `null`) et `indicators`
  (moyennes disponibles par indicateur), ainsi que les `weights` configurés.

Exemple de résultat contextualisé :

```json
{
  "journeys": [{
    "journey_id": "j1",
    "values": [0.2, 0.8],
    "score": 0.65,
    "indicators": [
      {"indicator_id": "lighting", "value": 0.2},
      {"indicator_id": "ridership", "value": 0.8}
    ]
  }],
  "weights": {"lighting": 0.25, "ridership": 0.75}
}
```

Les couleurs locales utilisent l'éclairage à pied/en attente, et la fréquentation
en transport. Pour le score global, les valeurs locales sont intégrées dans le
temps (interpolation linéaire entre sommets, prolongement aux limites du tronçon),
puis moyennées par durée pour chaque indicateur. Ces deux moyennes sont combinées
selon les poids configurés. Un indicateur sans portion applicable est exclu et
les poids restants renormalisés. Une donnée attendue mais manquante rend le score
global `null` si son poids est positif ; un poids nul ne bloque pas ce score.
Les valeurs locales restent évaluées même à poids nul ; une source illisible
provoque donc toujours une erreur 503. Sans durée positive ni poids applicable,
le score est `null`. Les poids n'affectent pas les couleurs locales.

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

Source : `src/safety/luminosite_log.tif`, livré sur la branche `victoria`
(Lambert 93 / EPSG:2154, maille de 130 m). Ce raster est **déjà en échelle
logarithmique**, avec des valeurs de 0 à 100 dont l'unité n'est pas documentée.
`luminosite.tif` (échelle linéaire d'origine) est conservé mais n'est plus utilisé.

Calcul : position WGS84 → reprojection dans le CRS du raster (pyproj) → pixel
contenant la position → valeur brute (rasterio) → score linéaire `valeur / 100`.
Aucun logarithme n'est appliqué par le service, pour ne pas l'appliquer deux fois.

Si la valeur brute est strictement inférieure à 50 (50 % de l'échelle du raster),
le score est ramené à **0** pour accentuer le contraste des zones peu éclairées.
À partir de 50 inclus, le score reste `valeur / 100` : 50 donne 0,5 et 100 donne 1.
Ce seuil est un choix de modélisation, pas une mesure physique ni une preuve de danger.

Exemples : Châtelet ≈ 0,80, bois de Vincennes = 0 (valeur brute ≈ 18).
Une position hors du raster ou sans donnée (nodata) n'a pas de score. Une valeur
brute hors de [0, 100] est traitée comme une donnée invalide (503).

## Indicateur `ridership`

Le CSV de `services/ridership` est chargé une fois, au premier appel. Un arc est
recherché par correspondance **exacte** de `gtfs_trip_id`, `from_stop`, `to_stop`,
`start_time` et `end_time` (instants comparés en UTC). Aucun rapprochement spatial
ni report d'une autre date n'est effectué. Arc inconnu : indice local `null`.

Le champ `estimated_validations_per_service_adjusted` est déjà un score inversé
entre 0 et 100 : 100 correspond à une faible fréquentation estimée. Le provider
applique **`1 - valeur / 100`**, sans nouveau logarithme ni écrêtage. Une valeur
vide, non finie, hors bornes, un schéma invalide ou des doublons contradictoires
provoquent une erreur 503. Il s'agit de validations estimées par service, **pas
d'une occupation observée**. Le sens favorable associé à la fréquentation est
une hypothèse de modélisation, pas une preuve de sécurité.

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