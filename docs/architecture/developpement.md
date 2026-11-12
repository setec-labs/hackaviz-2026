# Développement

## Outils

| Outil | Usage |
|---|---|
| [uv](https://docs.astral.sh/uv/) | environnement Python du monorepo (ne pas utiliser pip ni Poetry) |
| Node.js + npm | frontend |
| Git LFS | données volumineuses |

```bash
uv sync --all-packages                          # toutes les briques Python
uv add --package <brique> <dépendance>          # ajouter une dépendance à une brique
uv run --package <brique> <commande>            # lancer une commande dans une brique
```

!!! warning "Arrêter les services avant `uv sync`"
    Sous Windows, un `uv sync` lancé pendant que les services tournent peut laisser une bibliothèque à
    moitié installée (par exemple pyproj). En cas d'erreur d'import :
    `uv sync --all-packages --reinstall-package <paquet>`.

## Lancer les services

```bash
uv run python scripts/run_services.py                       # routing, safety et frontend
uv run python scripts/run_services.py --only safety frontend
uv run python scripts/run_services.py --reload              # redémarrage à chaud des services Python
uv run python scripts/run_services.py --skip-optimize       # sans régénérer journeys.min.json
```

Le script est en Python pour fonctionner sous Windows, macOS et Linux. Un arrêt (Ctrl+C) ou l'échec
d'un service arrête les autres.

## Tests

```bash
uv run --package safety python -m unittest discover -s services/safety/tests
uv run --package routing python -m unittest discover -s services/routing/tests
uv run python -m unittest discover -s scripts/tests
cd frontend && npm run typecheck && npm test
```

## Documentation

Cette documentation est générée avec [Zensical](https://zensical.org/) à partir du dossier `docs/` et
du fichier `zensical.toml`.

```bash
uv run zensical serve     # aperçu sur http://localhost:8000, rechargé à chaque modification
uv run zensical build     # site statique dans site/ (non versionné)
```

## Intégration continue et publication

Le workflow [`.github/workflows/ci.yml`](https://github.com/setec-labs/hackaviz-2026/blob/develop/.github/workflows/ci.yml)
s'exécute à chaque push sur `develop` ou `main`, et à chaque pull request qui les cible :

1. **Tests Python** (safety, routing, scripts) et **tests frontend** (typecheck, Vitest). Les données
   Git LFS ne sont pas téléchargées : les tests qui en dépendent sont ignorés.
2. **Documentation**, après des tests réussis, pour les pushs uniquement : `scripts/build_pages.py`
   construit les deux versions et les publie sur GitHub Pages.

| Branche | Adresse |
|---|---|
| `main` (stable) | racine du site |
| `develop` | `/dev/`, avec un bandeau « Documentation de développement » |

Les deux versions sont reconstruites à chaque déploiement, puisque GitHub Pages n'héberge qu'un site.
Tant que `main` n'a pas de documentation, la racine redirige vers `/dev/`.

!!! note "Réglages GitHub nécessaires (une seule fois)"
    - *Settings → Pages → Source* : **GitHub Actions**.
    - *Settings → Environments → github-pages* : autoriser la branche **develop** en plus de `main`.

## Règles de contribution

- **Git** : branche personnelle → `develop` → `main`. Pas de modification directe de `main`.
- **Code métier dans sa brique**, seuls les contrats réellement partagés vont dans `src/hackaviz_2026/`.
- **Contrats Pydantic** pour tout échange entre briques.
- **Pipeline d'itinéraires** (`transit_accessibility.py`, `run_scenarios.py`) : maintenu par l'expert
  métier, ne pas le modifier sans lui.
- **Pas de valeur inventée en silence**, et un indicateur n'est jamais présenté comme une preuve de danger.

Chaque brique a un fichier `AGENTS.md` qui détaille ses conventions, notamment la marche à suivre pour
ajouter un indicateur à safety. Voir aussi `CONTRIBUTING.md`.
