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
- **Résultat** : ~10 Mo par scénario, ~14 % des points conservés, ouverture en moins d'une demi-seconde.
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
