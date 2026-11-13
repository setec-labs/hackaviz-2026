# Contribuer à Noctambulle

Ce document explique comment installer le projet, travailler sur sa branche et contribuer aux différentes briques.

Le projet utilise **Python**, **uv** pour la gestion des dépendances et **Git** pour le travail collaboratif.

## Structure du projet

Le dépôt contient plusieurs briques Python regroupées dans un même workspace `uv`.

```text
hackaviz-2026/
├── src/
│   └── hackaviz_2026/      # Code et modèles communs
│
├── frontend/                # Application de visualisation
│   └── pyproject.toml
│
├── services/
│   ├── routing/             # Service lié aux trajets
│   │   └── pyproject.toml
│   └── safety/              # Service lié aux indicateurs de sécurité
│       └── pyproject.toml
│
├── scripts/
│   └── run_services.py      # Lance les services et le frontend en local
│
├── pyproject.toml           # Configuration principale du workspace
├── uv.lock                  # Versions exactes des dépendances
└── CONTRIBUTING.md
```

Chaque brique peut avoir ses propres dépendances Python.

Le package `hackaviz_2026` contient le code partagé entre les différentes briques, notamment les modèles et interfaces Pydantic communs.

---

# 1. Installer le projet

## Installer uv

La documentation officielle de uv est disponible ici :

https://docs.astral.sh/uv/

Sous Windows, uv peut notamment être installé avec :

```powershell
winget install --id=astral-sh.uv -e
```

Vérifier ensuite l'installation :

```powershell
uv --version
```

## Cloner le projet

```powershell
git clone <URL_DU_REPOSITORY>
cd hackaviz-2026
```

## Installer les dépendances

Il suffit ensuite d'exécuter :

```powershell
uv sync
```

`uv` va automatiquement :

- créer l'environnement Python `.venv` si nécessaire ;
- installer les dépendances ;
- utiliser les versions définies dans `uv.lock` ;
- préparer les différents projets du workspace.

Il n'est normalement pas nécessaire de lancer manuellement `pip install`.

## Lancer les services en local

Le script multiplateforme `scripts/run_services.py` (bibliothèque standard uniquement) démarre en une
commande :

| Service | URL |
|---|---|
| routing | <http://localhost:8001/docs> |
| safety | <http://localhost:8002/docs> |
| frontend | <http://localhost:5173> |

```powershell
uv run python scripts/run_services.py                            # tous les services
uv run python scripts/run_services.py --only safety frontend     # une sélection
uv run python scripts/run_services.py --reload                   # rechargement des services Python
```

Chaque ligne de sortie est préfixée par le nom du service. `Ctrl+C` arrête tous les services ; si l'un
d'eux s'arrête (port déjà utilisé, erreur au démarrage), les autres sont arrêtés aussi. Le frontend
nécessite au préalable `npm install` dans `frontend/`.

Tests du script : `uv run python -m unittest discover -s scripts\tests -v`.

---

# 2. Workflow Git

Nous utilisons trois niveaux de branches :

```text
main
 │
 └── develop
      │
      ├── florian
      ├── alice
      ├── bob
      └── ...
```

## `main`

Contient la version stable du projet.

On évite de travailler directement dessus.

## `develop`

Branche d'intégration commune.

Les développements terminés sont fusionnés dans `develop` afin de tester que les différentes briques fonctionnent ensemble.

## Branche personnelle

Chaque participant dispose de sa propre branche de développement.

Par exemple :

```text
florian
```

Les modifications quotidiennes sont réalisées sur cette branche.

---

# 3. Commencer à travailler

Toujours récupérer les dernières modifications :

```powershell
git checkout develop
git pull
```

Puis revenir sur sa branche :

```powershell
git checkout florian
```

Et récupérer les évolutions de `develop` :

```powershell
git merge develop
```

Vous pouvez ensuite travailler normalement.

---

# 4. Enregistrer ses modifications

Vérifier les fichiers modifiés :

```powershell
git status
```

Ajouter les modifications :

```powershell
git add .
```

Créer un commit :

```powershell
git commit -m "Ajout de la visualisation des trajets"
```

Puis envoyer la branche sur GitHub :

```powershell
git push
```

---

# 5. Proposer son travail

Lorsque votre développement fonctionne :

1. pousser les dernières modifications sur votre branche ;
2. ouvrir une Pull Request sur GitHub ;
3. sélectionner `develop` comme branche cible ;
4. décrire rapidement ce qui a été ajouté ou modifié.

Le chemin normal est donc :

```text
branche personnelle
        ↓
   Pull Request
        ↓
     develop
        ↓
      tests
        ↓
       main
```

Évitez de fusionner directement une branche personnelle dans `main`.

---

# 6. Ajouter une dépendance Python

Évitez :

```powershell
pip install ...
```

Utilisez `uv add` afin que la dépendance soit correctement enregistrée dans le projet.

Par exemple, pour ajouter `pandas` à une brique :

```powershell
uv add --package <nom-package> pandas
```

Exemple avec plusieurs bibliothèques :

```powershell
uv add --package <nom-package> pandas geopandas shapely
```

Cela met à jour automatiquement la configuration du projet et le fichier `uv.lock`.

Consultez le README de chaque brique pour connaître son nom de package et ses commandes spécifiques.

---

# 7. Exécuter une commande Python

Pour exécuter Python dans l'environnement du projet :

```powershell
uv run python ...
```

Pour travailler spécifiquement avec un membre du workspace :

```powershell
uv run --package <nom-package> ...
```

Par exemple :

```powershell
uv run --package <nom-package> python -m mon_module
```

---

# 8. Modifier les interfaces communes

Les objets échangés entre plusieurs services doivent autant que possible être définis dans :

```text
src/hackaviz_2026/
```

En particulier, les modèles Pydantic communs permettent aux différentes briques de partager les mêmes contrats de données.

Avant de modifier une interface commune, vérifiez donc son utilisation par les autres briques.

---

# 9. Avant de pousser

Quelques vérifications simples :

```powershell
git status
uv sync
```

Puis exécutez la brique sur laquelle vous avez travaillé.

L'objectif est simple : éviter d'envoyer volontairement sur `develop` quelque chose qui ne démarre plus.

---

# En cas de doute

Ne restez pas bloqué.

Demandez aux autres membres de l'équipe avant de modifier en profondeur :

- la structure du projet ;
- une interface commune ;
- le workspace `uv` ;
- les modèles Pydantic partagés ;
- le fonctionnement d'une autre brique.

Pendant le hackathon, une solution simple et comprise par toute l'équipe vaut généralement mieux qu'une architecture parfaite mais difficile à maintenir.