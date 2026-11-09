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

Dans le cas d'une API FastAPI :

```powershell
uv run --package safety uvicorn safety.main:app --reload
```

Adaptez le chemin du module à la structure réelle du service.

## Modèles de données communs

Les structures échangées avec les autres briques doivent autant que possible utiliser les modèles communs définis dans :

```text
src/hackaviz_2026/
```

Par exemple, un trajet, un point géographique ou un indicateur partagé ne devrait idéalement pas avoir trois définitions différentes dans trois services.

## Contribution

Travaillez sur votre branche personnelle puis créez une Pull Request vers `develop`.

Le workflow Git complet est décrit dans le `CONTRIBUTING.md` situé à la racine du repository.