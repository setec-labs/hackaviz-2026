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

`services/safety/` évalue des indicateurs d'environnement nocturne en un point.

| Route | Rôle |
|---|---|
| `GET /indicators` | liste des indicateurs disponibles |
| `POST /evaluate` | scores de tous les indicateurs en une position |
| `POST /score` | score global pondéré en une position |
| `POST /safety-index` | indice pour un lot de positions (5 000 au plus), utilisé par la carte |

Chaque indicateur est un **provider** qui respecte une interface commune :

```python
class IndicatorProvider(Protocol):
    id: str
    name: str
    description: str

    async def evaluate(self, position: Position) -> float:
        """Retourne un score normalisé entre 0.0 et 1.0."""
```

Le seul provider actuel, `LightingIndicatorProvider` (`lighting.py`), reprojette la position en
Lambert 93 avec pyproj, lit le pixel du raster avec rasterio et divise la valeur par 100.

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

## Modèles partagés

Les contrats échangés sont définis une seule fois dans `src/hackaviz_2026/` :

| Fichier | Contenu |
|---|---|
| `models.py` | `Position`, `Indicator`, `IndicatorResult`, requêtes et réponses de safety |
| `routing.py` | `Journey`, `JourneyLeg`, `ScenarioDocument`, `ScenarioSummary`, `Scenario`, rapport |
| `api.py` | formats d'erreur communs |

Les contraintes (latitude entre -90 et 90, score entre 0 et 1, poids positifs…) sont portées par les
modèles eux-mêmes, pas vérifiées à la main dans les routes.
