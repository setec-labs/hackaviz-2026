# Frontend

Cette brique contient l'interface de visualisation du projet Hackaviz 2026.

Elle permet notamment d'afficher les données et résultats produits par les différents services sous forme de cartes et de visualisations interactives.

## Installation

Depuis la racine du repository :

```powershell
uv sync
```

Il n'est pas nécessaire de créer un environnement Python spécifique au frontend.

## Ajouter une bibliothèque

Les dépendances utilisées uniquement par le frontend doivent être ajoutées au projet frontend et non au projet racine.

Depuis la racine :

```powershell
uv add --package frontend <librairie>
```

Par exemple :

```powershell
uv add --package frontend plotly
```

Plusieurs bibliothèques peuvent être ajoutées simultanément :

```powershell
uv add --package frontend plotly pandas
```

`uv` met automatiquement à jour le `pyproject.toml` et le `uv.lock`.

Évitez d'utiliser directement :

```powershell
pip install ...
```

## Exécuter le frontend

Depuis la racine :

```powershell
uv run --package frontend <commande>
```

La commande exacte de démarrage sera précisée ici en fonction de la technologie utilisée pour l'interface.

## Où travailler ?

Le code spécifique à l'interface doit rester dans cette brique.

Le code ou les modèles nécessaires à plusieurs briques ont plutôt vocation à être placés dans le package commun :

```text
src/hackaviz_2026/
```

## Avant de pousser vos modifications

Vérifiez que l'application démarre correctement puis poussez vos modifications sur votre branche personnelle.

La Pull Request devra cibler la branche `develop`.