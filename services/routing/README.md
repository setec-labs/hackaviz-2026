# Routing Service

Cette brique est responsable des fonctionnalités liées aux trajets et aux temps de parcours.

Elle expose les traitements nécessaires aux autres composants du projet, notamment au frontend.

## Installation

Depuis la racine du repository :

```powershell
uv sync
```

`uv` installe automatiquement les dépendances nécessaires au workspace.

## Ajouter une bibliothèque

Une dépendance spécifique au service Routing doit être ajoutée à ce projet :

```powershell
uv add --package routing <librairie>
```

Par exemple :

```powershell
uv add --package routing httpx
```

ou :

```powershell
uv add --package routing fastapi httpx
```

Évitez :

```powershell
pip install ...
```

La dépendance doit être déclarée afin que les autres participants puissent retrouver exactement le même environnement.

## Exécuter le service

Depuis la racine :

```powershell
uv run --package routing <commande>
```

Si le service utilise FastAPI et Uvicorn, la commande prendra par exemple la forme :

```powershell
uv run --package routing uvicorn routing.main:app --reload
```

Adaptez le chemin du module à la structure réelle du service.

## Interfaces communes

Si ce service échange des objets avec le frontend ou d'autres services, utilisez autant que possible les modèles Pydantic communs situés dans :

```text
src/hackaviz_2026/
```

Cela évite de définir plusieurs fois des structures légèrement différentes pour représenter les mêmes données.

## Contribution

Travaillez sur votre branche personnelle.

Lorsque votre modification fonctionne :

1. committez ;
2. poussez votre branche ;
3. créez une Pull Request vers `develop`.

Consultez le `CONTRIBUTING.md` situé à la racine pour le workflow complet.