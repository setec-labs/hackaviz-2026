# Instructions pour les agents du service safety

## Responsabilite

Le service safety calcule des indicateurs lies a l'environnement nocturne et les expose via une API FastAPI.

Un indicateur defavorable ne doit jamais etre presente comme une preuve objective de danger.

## Structure

- `src/safety/main.py` : application FastAPI, routes et gestionnaires d'erreurs HTTP.
- `src/safety/service.py` : `IndicatorService`, orchestration des providers et calcul du score global.
- `src/safety/providers.py` : protocole `IndicatorProvider` et implementations des indicateurs.
- `tests/test_api.py` : tests des modeles, du service et des routes.
- Les modeles Pydantic echanges (`Position`, `Indicator`, `IndicatorResult`, `EvaluateRequest`,
  `EvaluateResponse`, `IndicatorWeight`, `ScoreRequest`, `ScoreResponse`) sont definis dans
  `src/hackaviz_2026/models.py`. Ne pas les dupliquer dans ce service.

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
- `501` : indicateur non implemente (`IndicatorNotImplementedError`).
- `500` : un provider retourne une valeur hors `[0, 1]` ; c'est un bug du provider.

## Score global

- Moyenne ponderee des scores des indicateurs demandes, donc comprise dans `[0, 1]`.
- Les poids sont divises par le poids maximal avant la somme pour eviter tout depassement
  numerique avec de tres grands poids.
- Un indicateur de poids nul est evalue et figure dans la reponse, sans influencer le score.
- L'ordre des `indicators` de la reponse suit l'ordre des `weights` de la requete.
- Si un indicateur demande n'est pas implemente, toute la requete echoue en `501` : ne pas
  ignorer silencieusement un indicateur ni renormaliser sans lui.

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
4. Lever une exception explicite si la position est hors de l'emprise des donnees ou si la
   donnee est absente ; ne pas inventer de valeur par defaut. Definir le code HTTP associe dans
   `main.py` si un nouveau type d'erreur est introduit.
5. Enregistrer le provider dans `get_indicator_service()` (`main.py`).
6. Charger les ressources couteuses (raster, fichiers) une seule fois plutot qu'a chaque appel ;
   ne pas les versionner dans le repository (`data/` est ignore).
7. Ajouter les dependances avec `uv add --package safety <dependance>` et versionner `uv.lock`.
8. Ajouter des tests : cas nominal, bornes du score, position hors emprise, donnee absente.
   Pour tester l'API sans donnees reelles, surcharger `get_indicator_service` via
   `app.dependency_overrides` avec des providers de test.

## Indicateur `lighting`

`LightingIndicatorProvider` est declare mais leve `NotImplementedError` (reponse `501`).

Implementation prevue :

```text
Position WGS84 (EPSG:4326)
    -> transformation vers le CRS du GeoTIFF si necessaire (pyproj)
    -> localisation du pixel
    -> extraction de la valeur brute du raster (rasterio)
    -> normalisation specifique a l'indicateur
    -> score [0, 1]
```

Points d'attention :

- utiliser `always_xy=True` avec pyproj pour garder l'ordre longitude/latitude ;
- gerer les valeurs `nodata` et les positions hors raster explicitement ;
- la strategie de normalisation reste a definir et a documenter.

## Integration frontend

Le client frontend provisoire attend une route batch `POST /safety-index` qui n'existe pas encore.
Toute evolution des contrats doit etre alignee avec `frontend/src/api/contracts.ts`.

## Validation

```text
uv run --package safety python -m unittest discover -s services\safety\tests -v
uv run --package safety uvicorn safety.main:app --reload
```

Apres une modification, executer les tests et verifier que l'API demarre.
