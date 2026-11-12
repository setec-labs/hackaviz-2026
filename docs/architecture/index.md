# Architecture

!!! info "Architecture de hackathon"
    L'objectif était d'avancer vite à plusieurs, sans se bloquer. Chaque brique a un périmètre clair et
    communique avec les autres par des contrats typés. Rien n'est prévu pour la production : pas
    d'authentification, pas de base de données, pas de déploiement.

## Vue d'ensemble

```mermaid
flowchart LR
    subgraph Préparation["Préparation hors ligne"]
        GTFS[(GTFS IDFM)] --> PIPE[Pipeline d'itinéraires]
        OSM[(Voirie OSM)] --> PIPE
        PIPE --> J[(journeys.json)]
        J --> OPT[optimize-scenarios]
        OPT --> JM[(journeys.min.json)]
        RAS[(Raster d'éclairage<br/>luminosite_log.tif)]
    end

    subgraph Services["Services"]
        R[routing<br/>FastAPI :8001]
        S[safety<br/>FastAPI :8002]
    end

    F[Frontend<br/>React + deck.gl :5173]

    JM --> R
    RAS --> S
    F -- "scénarios et trajets" --> R
    F -- "indice aux points<br/>de marche et d'attente" --> S
```

## Les briques

| Brique | Rôle | Détails |
|---|---|---|
| `frontend/` | carte, animation, légende, son | [Frontend](frontend.md) |
| `services/routing/` | calcul hors ligne des itinéraires et API des scénarios | [Services](services.md) |
| `services/safety/` | indicateurs d'environnement nocturne normalisés | [Services](services.md) |
| `src/hackaviz_2026/` | modèles Pydantic partagés entre les services | [Services](services.md#modeles-partages) |
| `scripts/` | lancement de tous les services en une commande | [Développement](developpement.md) |

## Décisions structurantes

- **Calcul hors ligne, lecture en ligne.** Calculer un scénario prend environ 30 minutes. L'API routing ne
  calcule rien : elle sert des fichiers déjà produits.
- **Deux services indépendants.** Les trajets et les indicateurs évoluent à des rythmes différents et
  sont portés par des personnes différentes.
- **Contrats Pydantic partagés.** Les modèles échangés sont définis une seule fois dans
  `src/hackaviz_2026/`, et validés côté frontend à la réception.
- **Le frontend choisit, safety évalue.** Le frontend sélectionne les points à évaluer (sommets des
  portions de marche et d'attente des trajets plausibles) et les envoie à safety par lots de 5 000.
- **Mode démonstration.** Le frontend fonctionne sans backend (`?source=mock`), ce qui a permis de
  développer la visualisation avant que les données soient prêtes.
