# Instructions pour les agents du service safety

## Responsabilite

Le service safety calcule des indicateurs lies a l'environnement nocturne et les expose via une API FastAPI.

Un indicateur defavorable ne doit jamais etre presente comme une preuve objective de danger.

## Structure

- `src/safety/main.py` : application FastAPI, routes et gestionnaires d'erreurs HTTP.
- `src/safety/service.py` : `IndicatorService`, orchestration des providers et calcul du score global.
- `src/safety/providers.py` : protocole `IndicatorProvider` et erreurs communes des providers
  (`IndicatorUnavailableError`, `IndicatorDataError`).
- `src/safety/lighting.py` : lecture du raster et `LightingIndicatorProvider`.
- `src/safety/luminosite_log.tif` : raster d'eclairage en echelle log livre par la branche `victoria`
  (`luminosite.tif`, l'ancienne version lineaire, n'est plus utilise).
- `tests/test_api.py` : tests des modeles, du service et des routes.
- `tests/test_lighting.py` : tests de l'eclairage sur des GeoTIFF synthetiques et sur le raster livre.
- Les modeles Pydantic echanges (`Position`, `Indicator`, `IndicatorResult`, `EvaluateRequest`,
  `EvaluateResponse`, `IndicatorWeight`, `ScoreRequest`, `ScoreResponse`, `SafetyIndexRequest`,
  `PositionSafetyIndex`, `SafetyIndexResponse`) sont definis dans `src/hackaviz_2026/models.py`.
  Ne pas les dupliquer dans ce service.

## Convention de score

Tout score expose par l'API est normalise : `0.0 <= score <= 1.0`.

- `0.0` = situation la moins favorable ;
- `1.0` = situation la plus favorable.

Cette convention est commune a tous les `IndicatorProvider`. La contrainte est portee par les
modeles Pydantic (`IndicatorResult.value`, `ScoreResponse.score`) : une valeur hors bornes, `NaN`
ou infinie produit une erreur et n'est jamais exposee.

La valeur brute d'une source (GeoTIFF, comptage, distance...) n'est pas exposee directement :
chaque provider applique sa propre normalisation avant de retourner son score.

## API

- `GET /indicators` -> `list[Indicator]` : metadonnees des providers enregistres.
- `POST /evaluate` (`EvaluateRequest`) -> `EvaluateResponse` : evalue tous les indicateurs.
- `POST /score` (`ScoreRequest`) -> `ScoreResponse` : evalue les indicateurs demandes et calcule
  leur moyenne ponderee.
- `POST /safety-index` (`SafetyIndexRequest`) -> `SafetyIndexResponse` : route batch consommee
  par le frontend. Au plus 5 000 points (`MAX_SAFETY_INDEX_POINTS`, aligne sur la taille de lot du
  client frontend). Les indices sont dans l'ordre des points ; `value` est la moyenne a poids egaux
  de tous les indicateurs, ou `null` si l'un d'eux n'a pas de donnee a cette position.

Regles :

- chaque route declare un modele de requete et un `response_model` Pydantic explicites ;
- la validation est portee par Pydantic, pas par du code manuel dans les routes ;
- les routes delegent a `IndicatorService` et ne manipulent pas les providers directement ;
- les coordonnees sont en WGS84 (EPSG:4326).

Codes d'erreur :

- `422` : entree invalide (coordonnees hors bornes, nombre non fini, poids negatif, identifiants
  dupliques, aucun poids strictement positif). Le gestionnaire `RequestValidationError` renvoie
  un `ValidationErrorResponse` afin de ne pas echouer sur des valeurs non serialisables.
- `400` : identifiant d'indicateur inconnu (`UnknownIndicatorError`).
- `404` : aucune donnee ne couvre la position (`IndicatorUnavailableError`) pour `/evaluate` et
  `/score`. Dans `/safety-index`, ce cas donne `value: null` pour le point concerne, sans faire
  echouer le lot.
- `501` : indicateur non implemente (`IndicatorNotImplementedError`), y compris dans le lot.
- `503` : donnee source absente, illisible ou incoherente (`IndicatorDataError`), ou variable
  d'environnement de configuration vide.
- `500` : un provider retourne une valeur hors `[0, 1]` ; c'est un bug du provider.

## Score global

- Moyenne ponderee des scores des indicateurs demandes, donc comprise dans `[0, 1]`.
- Les poids sont divises par le poids maximal avant la somme pour eviter tout depassement
  numerique avec de tres grands poids.
- Un indicateur de poids nul est evalue et figure dans la reponse, sans influencer le score.
- L'ordre des `indicators` de la reponse suit l'ordre des `weights` de la requete.
- Si un indicateur demande n'est pas implemente, toute la requete echoue en `501` : ne pas
  ignorer silencieusement un indicateur ni renormaliser sans lui.
- Meme regle pour `/safety-index` : si un indicateur manque a une position, l'indice vaut `null`
  au lieu d'etre calcule avec les seuls indicateurs disponibles.

## Ajouter un indicateur

1. Creer une classe dans `providers.py` (ou un module dedie si elle grossit) respectant
   `IndicatorProvider` :
   - attributs `id` (stable, snake_case, unique), `name`, `description` ;
   - methode `async def evaluate(self, position: Position) -> float` retournant le score
     normalise final.
2. Implementer la chaine : donnee brute -> normalisation propre a l'indicateur -> score `[0, 1]`.
   Documenter la strategie de normalisation et le sens du score (1 = plus favorable).
3. Tant que le calcul n'est pas pret, lever `NotImplementedError`. Ne jamais retourner de
   valeur fictive.
4. Lever `IndicatorUnavailableError` si la position est hors de l'emprise des donnees ou sans
   donnee, et `IndicatorDataError` si la source est absente, illisible ou contient une valeur
   brute inattendue. Ne pas inventer de valeur par defaut ni borner silencieusement (`clip`).
   Definir le code HTTP dans `main.py` si un nouveau type d'erreur est introduit.
5. Enregistrer le provider dans `get_indicator_service()` (`main.py`). Ajouter un provider modifie
   aussi `/safety-index`, qui fait la moyenne de tous les indicateurs : verifier l'effet sur le
   frontend.
6. Charger les ressources couteuses (raster, fichiers) une seule fois : `get_indicator_service`
   est mis en cache (`lru_cache`) et les providers chargent leurs donnees au premier appel
   (voir `LightingIndicatorProvider._get_raster`). Rendre le chemin configurable par une variable
   d'environnement. Les donnees volumineuses vont dans `data/` (ignore par Git).
7. Ajouter les dependances avec `uv add --package safety <dependance>` et versionner `uv.lock`.
8. Ajouter des tests : cas nominal, bornes du score, position hors emprise, donnee absente.
   Pour tester l'API sans donnees reelles, surcharger `get_indicator_service` via
   `app.dependency_overrides` avec des providers de test. Pour un raster, generer un petit
   GeoTIFF synthetique dans un dossier temporaire (voir `tests/test_lighting.py`). Apres un
   test qui modifie l'environnement, appeler `get_indicator_service.cache_clear()`.

## Indicateur `lighting`

`LightingIndicatorProvider` (`lighting.py`) lit `luminosite_log.tif` (configurable avec
`SAFETY_LIGHTING_RASTER`) :

```text
Position WGS84 (EPSG:4326)
    -> reprojection dans le CRS du raster (pyproj, always_xy=True)
    -> pixel contenant la position (transformation affine inverse, arrondi vers le bas)
    -> valeur brute (rasterio, bande 1, nodata masque)
    -> normalize_lighting : 0 si valeur < 50, sinon valeur / 100
    -> score [0, 1]
```

Caracteristiques du raster livre : Lambert 93 (EPSG:2154), maille de 130 m, valeurs brutes
de 0 a 100 deja en echelle logarithmique (unite non documentee), environ 37 % de pixels nodata.

Decisions :

- seuil : une valeur brute strictement inferieure a 50 donne 0 ; a partir de 50 inclus,
  normalisation **lineaire** `valeur / 100`. Ce seuil accentue le contraste des zones peu
  eclairees, sans constituer une preuve de danger. Le log est deja applique en amont dans le
  raster (`luminosite_log.tif`, branche `victoria`). Ne pas rajouter de log dans le service, il
  serait applique deux fois. Historique : un `log(1 + v) / log(101)` etait applique sur
  `luminosite.tif` car en lineaire 98,5 % de Paris tombait sous 0,25. Avec le raster log :
  Chatelet ~0,80, bois de Vincennes = 0 (valeur brute ~18). Pour changer de strategie, modifier uniquement
  `normalize_lighting`, puis ses tests et la documentation ;
- position hors raster, nodata ou `NaN` -> `IndicatorUnavailableError` ;
- valeur brute hors `[0, 100]` -> `IndicatorDataError`, sans la borner ;
- le raster est charge entierement en memoire (environ 5 Mo) au premier appel. Un lot de
  5 000 points est evalue en environ 0,1 s.

## Integration frontend

Le frontend appelle `POST /safety-index` (`frontend/src/api/http/fastApiClients.ts`) par lots de
5 000 points. CORS autorise par defaut le serveur Vite (`http://localhost:5173`, configurable
avec `SAFETY_CORS_ORIGINS`). Toute evolution de ce contrat doit etre alignee avec
`frontend/src/api/contracts.ts` et `frontend/src/api/validation.ts`.

## Validation

```text
uv run --package safety python -m unittest discover -s services\safety\tests -v
uv run --package safety uvicorn safety.main:app --port 8002 --reload
uv run python scripts/run_services.py   # tous les services et le frontend
```

Apres une modification, executer les tests et verifier que l'API demarre.
