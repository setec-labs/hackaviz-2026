# Instructions GitHub Copilot du projet

## Contexte

Ce repository contient le projet Hackaviz Mobilites 2026 de l'equipe setec.

Le projet propose une cartographie interactive des trajets de nuit en Ile-de-France afin d'explorer les liens entre :

- le temps de parcours ;
- l'accessibilite ;
- l'environnement nocturne ;
- les indicateurs pouvant contribuer au sentiment de securite.

L'absence d'eclairage ou un indicateur defavorable ne doit pas etre presente comme une preuve qu'un lieu est dangereux.

## Architecture

Le repository est un monorepo Python gere avec uv.

Les principales briques sont :

- `frontend/` : application de visualisation ;
- `services/routing/` : calcul et traitement des trajets ;
- `services/safety/` : calcul des indicateurs lies a l'environnement nocturne ;
- `src/hackaviz_2026/` : modeles Pydantic et interfaces partages.

## Gestion Python

Utiliser uv pour toutes les operations liees a Python.

Ne pas utiliser directement `pip install`, `python -m venv` ou Poetry pour modifier l'environnement du projet.

Pour ajouter une dependance a une brique :

```text
uv add --package <nom-du-package> <dependance>
```

Pour lancer une commande :

```text
uv run --package <nom-du-package> <commande>
```

Le fichier `uv.lock` doit etre mis a jour et versionne lorsqu'une dependance change.

## Regles d'architecture

- Placer le code metier dans la brique concernee.
- Placer dans `src/hackaviz_2026/` uniquement le code reellement partage.
- Utiliser Pydantic pour definir les contrats de donnees echanges entre les briques.
- Ne pas dupliquer un modele partage dans plusieurs services.
- Eviter les dependances circulaires entre les briques.
- Ne pas restructurer plusieurs briques sans necessite explicite.
- Preferer une solution simple, lisible et adaptee a un hackathon.

## Qualite du code

- Utiliser la version Python declaree dans le projet.
- Ajouter des annotations de type aux fonctions publiques.
- Utiliser des noms explicites en anglais dans le code.
- Rediger des commentaires uniquement lorsqu'ils expliquent une decision non evidente.
- Eviter les fonctions trop longues et les abstractions prematurees.
- Ne pas inventer de donnees ou de comportement silencieux.
- Valider les donnees externes avant leur utilisation.

## Tests

Lorsqu'une fonctionnalite est ajoutee ou modifiee :

- ajouter ou mettre a jour les tests associes ;
- tester les cas nominaux ;
- tester les entrees absentes ou invalides ;
- verifier les modeles Pydantic concernes ;
- signaler clairement les tests qui n'ont pas pu etre executes.

Ne pas supprimer un test uniquement pour faire passer la suite de tests.

## Frontend

Respecter la documentation frontend et la palette graphique du projet.

Couleurs principales :

- fond : `#061B3A` ;
- surface : `#0B2F5B` ;
- reseau : `#286FAE` ;
- trajet : `#35C5F4` ;
- selection : `#8DE5FA` ;
- texte : `#F3F8FC` ;
- vigilance : `#FFBF47` ;
- vigilance elevee : `#FF7A45`.

La couleur ne doit pas etre le seul moyen de transmettre une information.

## Git

Le workflow du projet est :

```text
branche personnelle -> develop -> main
```

- Ne pas modifier directement `main`.
- Les Pull Requests des branches personnelles ciblent `develop`.
- Avant de proposer une modification, synchroniser les dependances, executer les tests pertinents et verifier que la brique modifiee demarre.
