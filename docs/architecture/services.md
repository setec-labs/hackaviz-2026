# Services

Les deux services sont des applications **FastAPI** en Python 3.14. Leurs contrats sont des modèles
**Pydantic v2** et la documentation interactive est générée automatiquement :

- routing : <http://localhost:8001/docs>
- safety : <http://localhost:8002/docs>

## Routing

`services/routing/` contient deux choses distinctes :

1. **Le pipeline de calcul** (`transit_accessibility.py`, `run_scenarios.py`) : il produit les trajets de
   chaque scénario, hors ligne, en environ 30 minutes par scénario. Il est maintenu par l'expert métier de
   l'équipe et n'est pas modifié par l'API.
2. **L'API de lecture**, qui sert les fichiers produits.

| Route | Rôle |
|---|---|
| `GET /scenarios` | liste des scénarios (identifiant, nom, description, départ) |
| `GET /scenarios/{id}` | un scénario complet, avec ses trajets et leurs tronçons |
| `POST /report` | bilan d'un scénario : **non implémenté**, répond 501 |

Organisation du code :

| Fichier | Rôle |
|---|---|
| `main.py` | routes FastAPI et gestion des erreurs |
| `service.py` | logique applicative |
| `repository.py` | lecture des scénarios sur disque, avec un petit cache |
| `providers.py` | interfaces des sources de scénarios et de rapports |
| `optimize.py` | commande `optimize-scenarios` (voir [Données](donnees.md)) |

L'en-tête de chaque fichier est lu sans charger les trajets, pour que la liste des scénarios reste
instantanée.

## Safety

`services/safety/` évalue des indicateurs d'environnement nocturne en une position ou
dans le contexte d'un trajet. Les providers sont créés par une dépendance FastAPI
mise en cache ; les deux rasters et le CSV sont chargés au premier usage, puis réutilisés.

| Route | Rôle |
|---|---|
| `GET /indicators` | liste des indicateurs disponibles |
| `POST /evaluate` | scores des indicateurs de position (éclairage et densité) |
| `POST /score` | score global pondéré en une position |
| `POST /safety-index` | API historique : indicateurs de position (5 000 points au plus) |
| `POST /journey-safety` | indices locaux et score global pondéré, utilisé par la carte |

Chaque indicateur est un **provider** qui respecte une interface commune :

```python
class IndicatorProvider(Protocol):
    id: str
    name: str
    description: str

    async def evaluate(self, position: Position) -> float:
        """Retourne un score normalisé entre 0.0 et 1.0."""
```

`LightingIndicatorProvider` (`lighting.py`) reprojette la position en
Lambert 93 avec pyproj et lit le pixel du raster avec rasterio. Une valeur strictement inférieure
à 50 donne un score de 0 ; à partir de 50 inclus, la valeur est divisée par 100.

`RidershipIndicatorProvider` (`ridership.py`) évalue un **arc** via `evaluate_arc(JourneyLeg)`,
pas une position : il retrouve exactement le trajet GTFS, les arrêts et les instants dans le CSV.
Son score vaut `1 - estimated_validations_per_service_adjusted / 100`.
La source est configurable avec `SAFETY_RIDERSHIP_CSV` et chargée une seule fois.

`PopulationDensityIndicatorProvider` (`population_density.py`) lit `PresenceHum_IDF_OK.tif`
(EPSG:2154, maille de 100 m), via le lecteur commun `raster.py`.
Le score vaut `1 - valeur / 100` : 0 brut est favorable, 100 brut défavorable selon la convention
fournie. Il s'applique à la marche et à l'attente, pas au transport. Son chemin est configurable
avec `SAFETY_POPULATION_DENSITY_RASTER`. Ce n'est pas une mesure de présence nocturne observée.

`POST /journey-safety` reçoit les `Journey` partagés de routing et des `weights`
(`lighting`, `ridership`, `population_density`, un tiers chacun sans objet `weights`, somme 1).
Un ancien objet de poids sans densité conserve `population_density=0`.
Limites : 100 trajets et 5 000 coordonnées.
Le service retourne les valeurs locales par sommet et les moyennes temporelles par indicateur,
puis leur combinaison pondérée. L'indice local piéton est la moyenne à poids égaux
éclairage/densité, indépendante des préférences. Les indicateurs sans portion applicable sont exclus avec
renormalisation ; une donnée attendue manquante n'est jamais ignorée.

### Contrat de calcul d'un trajet

Le frontend transmet les `Journey` reçus de routing, sans supprimer leurs tronçons :

```json
{
  "journeys": ["… objets Journey complets …"],
  "weights": {"lighting": 0.25, "ridership": 0.5, "population_density": 0.25}
}
```

Cette illustration abrège les trajets ; un élément réel contient notamment `journey_id`,
`destination`, `start_time`, `end_time`, `legs`, `coordinates` et `offsets_s`.
Les schémas exécutables sont disponibles sur `/docs` et `/openapi.json`.

| Champ de réponse | Contrat |
|---|---|
| `journeys[].journey_id` | identifiant du trajet, dans l'ordre de la requête |
| `journeys[].values` | un score `[0, 1]` ou `null` par coordonnée, même ordre et même longueur |
| `journeys[].indicators` | moyennes temporelles disponibles de chaque indicateur |
| `journeys[].score` | moyenne pondérée globale dans `[0, 1]`, ou `null` |
| `weights` | trois poids effectifs, finis, positifs ou nuls, de somme 1 |

Une moyenne temporelle est calculée séparément pour chaque indicateur sur ses seules
portions applicables : éclairage et densité sur marche/attente, fréquentation sur transport.
Les échantillons des rasters sont interpolés dans le temps, avec prolongement aux limites
des tronçons ; la fréquentation est constante sur un arc. Les moyennes des tronçons sont
ensuite combinées selon leur durée, puis selon les poids configurés.

Les couleurs locales restent indépendantes de ces poids. Une source illisible provoque
une erreur 503 même lorsque son poids est nul : le service ne masque pas une source invalide.
Sans durée positive ni poids applicable, le score global est `null`.

### Configuration des services

| Variable | Rôle / valeur par défaut |
|---|---|
| `ROUTING_SCENARIOS_DIR` | `data/output/scenarios`, relatif au répertoire de lancement |
| `ROUTING_CORS_ORIGINS` | origines web autorisées, séparées par des virgules |
| `SAFETY_LIGHTING_RASTER` | `services/safety/src/safety/luminosite_log.tif` |
| `SAFETY_POPULATION_DENSITY_RASTER` | `services/safety/src/safety/PresenceHum_IDF_OK.tif` |
| `SAFETY_RIDERSHIP_CSV` | `data/output/ridership/ridership_by_transit_arc.csv` |
| `SAFETY_CORS_ORIGINS` | origines web autorisées, séparées par des virgules |

Les deux configurations CORS autorisent par défaut `http://localhost:5173` et
`http://127.0.0.1:5173`. Si le port ou le domaine du frontend change, adapter les
origines des **deux** services. Les chemins safety par défaut sont résolus depuis
le code installé ; une variable de chemin explicitement vide est une erreur 503.

!!! tip "Ajouter un indicateur"
    Créer un provider qui renvoie un score dans [0, 1] (1 = le plus favorable), l'enregistrer dans
    `main.py` et ajouter ses tests. La marche à suivre détaillée est dans `services/safety/AGENTS.md`.

### Codes d'erreur

| Code | Signification |
|---|---|
| 400 | indicateur inconnu dans les poids de `/score` |
| 404 | aucune donnée à cette position (hors du raster) pour `/evaluate` et `/score` |
| 422 | données invalides (latitude hors bornes, lot trop grand…) |
| 501 | indicateur déclaré mais pas encore implémenté |
| 503 | donnée source indisponible ou illisible (raster absent) |

Pour `/safety-index`, une position hors du raster n'est pas une erreur : sa valeur vaut `null`.
Pour `/journey-safety`, un arc inconnu ou un pixel manquant donne également une valeur locale
`null`, et un score global `null` si l'indicateur concerné a un poids positif.

## Modèles partagés

Les contrats échangés sont définis une seule fois dans `src/hackaviz_2026/` :

| Fichier | Contenu |
|---|---|
| `models.py` | `Position`, `Indicator`, `IndicatorResult`, requêtes et réponses de safety |
| `routing.py` | `Journey`, `JourneyLeg`, `ScenarioDocument`, `ScenarioSummary`, `Scenario`, rapport |
| `journey_safety.py` | `SafetyWeights`, requête et réponse de scores contextualisés ; réutilise `Journey` |
| `api.py` | formats d'erreur communs |

Les contraintes (latitude entre -90 et 90, score entre 0 et 1, poids positifs…) sont portées par les
modèles eux-mêmes, pas vérifiées à la main dans les routes.
