# Données

## Vue d'ensemble

| Donnée | Emplacement | Producteur | Stockage |
|---|---|---|---|
| Horaires GTFS IDFM | `data/input/IDFM-gtfs-0511/` | Île-de-France Mobilités | Git LFS (gros fichiers) |
| Voirie OSM | `data/input/osm/` | OpenStreetMap | Git LFS |
| Graphe piéton en cache | `data/output/transit_accessibility_cache/` | pipeline routing | Git LFS |
| Trajets par scénario | `data/output/scenarios/<id>/journeys.json` | pipeline routing | Git LFS (~150 Mo chacun) |
| Trajets allégés | `data/output/scenarios/<id>/journeys.min.json` | `optimize-scenarios` | non versionné, régénéré |
| Raster d'éclairage | `services/safety/src/safety/luminosite_log.tif` | équipe | Git (4 Mo) |
| Raster de contexte de densité | `services/safety/src/safety/PresenceHum_IDF_OK.tif` | Victoria | Git (7,6 Mo) |
| Fréquentation par arc | `data/output/ridership/ridership_by_transit_arc.csv` | pipeline ridership | Git |
| Bilan de couverture | `data/output/ridership/ridership_coverage_summary.json` | pipeline ridership | Git |

`destination.population` est une population résidente de commune ou d'arrondissement,
obtenue par le pipeline auprès de `geo.api.gouv.fr` ou de son cache. Elle détermine
la taille des bulles, pas le score de densité. Elle n'est ni un nombre de voyageurs
à l'arrivée ni une mesure de présence nocturne. Si ce champ manque, l'interface
utilise une population simulée, explicitement signalée dans l'infobulle.

## Format d'un scénario

Un fichier `journeys.json` contient un en-tête puis la liste des trajets. Extrait réel (raccourci) :

```json
{
  "name": "Pigalle-2h",
  "description": "Sortie_de_bar_à_Pigalle_à_2h",
  "origin": { "latitude": 48.882875, "longitude": 2.33312 },
  "departure_time": "2026-11-08T02:00:00+01:00",
  "journeys": [
    {
      "journey_id": "j-1",
      "destination": {
        "latitude": 48.3483, "longitude": 2.5648,
        "name": "Achères-la-Forêt (77001)", "population": 1191
      },
      "start_time": "2026-11-08T02:00:00+01:00",
      "end_time": "2026-11-08T16:29:45.512145+01:00",
      "legs": [
        {
          "mode": "walk_direct",
          "start_time": "2026-11-08T02:00:00+01:00",
          "end_time": "2026-11-08T16:29:45.512145+01:00",
          "from_stop": "ORIGIN", "to_stop": "DESTINATION:0",
          "gtfs_trip_id": null,
          "point_range": [0, 2556]
        }
      ],
      "coordinates": [[2.33312, 48.882875], [2.333238, 48.882764], "…"],
      "offsets_s": [0, "…"]
    }
  ]
}
```

Ce trajet est une marche directe de plus de 14 heures : un exemple typique de trajet affiché en gris
(voir [Scénarios et trajets](../metier/scenarios.md#trajets-de-plus-de-2-heures)).

Le contrat complet est défini par les modèles Pydantic `ScenarioDocument`, `Journey` et `JourneyLeg`
(`src/hackaviz_2026/routing.py`), qui vérifient notamment :

- `mode` vaut `walk_access`, `walk_transfer`, `walk_egress`, `walk_direct`, `wait` ou `transit` ;
- `point_range` est un intervalle **semi-ouvert** `[début, fin)` d'indices dans `coordinates`, et les
  tronçons couvrent tout le trajet, dans l'ordre et sans trou ;
- `offsets_s` donne, pour chaque coordonnée, le temps écoulé en secondes depuis le départ du trajet.

## Optimisation des scénarios

Les fichiers bruts pèsent environ 150 Mo par scénario : trop pour un navigateur. La commande
`optimize-scenarios` produit une version allégée :

```bash
uv run --package routing optimize-scenarios           # ne refait que ce qui a changé
uv run --package routing optimize-scenarios --force --tolerance-m 20
```

- **Algorithme** : simplification de Douglas-Peucker **dans l'espace et le temps**, tronçon par tronçon.
  Un point n'est retiré que si la position interpolée au même instant reste à moins de 10 m (par défaut)
  de la position réelle. L'animation reste donc fidèle aux vitesses, pas seulement au tracé.
- **Les limites de tronçons sont conservées** : les modes (marche, attente, transport) restent exacts.
- **Résultat** : environ 14 à 16 % des points conservés sur les onze scénarios livrés,
  avec la tolérance par défaut de 10 m. Le poids final et le temps de chargement dépendent
  du scénario, du disque et du navigateur ; ce n'est pas une garantie de latence.
- Le fichier produit est revalidé avec `ScenarioDocument` avant d'être écrit.

L'API préfère `journeys.min.json` tant qu'il n'est **pas plus ancien** que `journeys.json`, sinon elle lit
le fichier brut. `scripts/run_services.py` lance l'optimisation avant de démarrer les services : déposer un
nouveau scénario suffit.

## Raster d'éclairage

- Fichier `luminosite_log.tif`, Lambert 93 (EPSG:2154), maille de 130 m, valeurs 0 à 100 en échelle
  logarithmique.
- Chargé une seule fois en mémoire au premier appel du service safety.
- Chemin configurable par la variable d'environnement `SAFETY_LIGHTING_RASTER`.
- `luminosite.tif`, la première version en échelle linéaire, est conservé pour comparaison.

## Raster de densité de population

- Fichier `PresenceHum_IDF_OK.tif`, Lambert 93 (EPSG:2154), maille de 100 m.
- Indice préparé entre 0 et 100, et non une densité exprimée en habitants/km².
  Selon la convention fournie, 0 brut est favorable et 100 brut défavorable :
  safety applique `1 - valeur / 100`.
- Même lecteur (`raster.py`) et même politique de couverture que l'éclairage :
  hors emprise ou nodata reste indisponible ; une source illisible ou une valeur finie
  hors bornes est une erreur, pas une valeur de repli.
- Chargement paresseux en mémoire, chemin configurable par `SAFETY_POPULATION_DENSITY_RASTER`.
- La construction amont de cet indice reste à documenter. Voir les
  [hypothèses et limites des indicateurs](../metier/indicateurs.md).

## Fréquentation par arc

Le script `services/ridership/ridership_surface.py` produit un CSV et un bilan de couverture
à partir des scénarios, des horaires GTFS et des fichiers de validations.
Il n'est pas lancé par les requêtes HTTP : le service safety lit les résultats déjà produits.
La méthode métier, les imputations et les ratios de véhicule sont conservés dans le
[README du pipeline ridership](https://github.com/setec-labs/hackaviz-2026/blob/develop/services/ridership/README.md).

Safety utilise le champ `estimated_validations_per_service_adjusted`, déjà préparé entre
0 et 100, et calcule `1 - valeur / 100`. La clé d'un arc est le quintuplet
`gtfs_trip_id`, `from_stop`, `to_stop`, `start_time`, `end_time` (instants comparés en UTC).
Il n'y a pas de rapprochement spatial ni de report sur une autre date : un arc inconnu
reste sans donnée. Le CSV est chargé une fois et peut être configuré avec `SAFETY_RIDERSHIP_CSV`.
