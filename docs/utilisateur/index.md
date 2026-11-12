# Démarrer

Cette page explique comment lancer l'application sur un poste. Pour la lecture de la carte, voir
[Lire la carte](carte.md).

## Prérequis

| Outil | Rôle | Installation |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | Python et dépendances des services | [Instructions d'installation](https://docs.astral.sh/uv/getting-started/installation/) ; sous Windows : `winget install --id=astral-sh.uv -e` |
| [Node.js](https://nodejs.org/) 20+ | interface web | installeur officiel |
| [Git](https://git-scm.com/) et [Git LFS](https://git-lfs.com/) | dépôt et fichiers de scénarios volumineux | installer Git et Git LFS, puis exécuter `git lfs install` |
| Navigateur récent | Chrome, Edge ou Firefox, avec accélération matérielle | — |

Une connexion Internet est nécessaire pour le fond de carte. Sans elle, les trajets s'affichent sur un fond
uni.

### Outils de compilation

Certaines dépendances Python comportent du code natif. Si aucun paquet précompilé compatible n'est
disponible, leur installation peut nécessiter un compilateur et des bibliothèques supplémentaires.

**Windows.** Installer [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
avec le composant « Développement Desktop en C++ » (compilateur MSVC et SDK Windows). Une version
Microsoft Visual C++ **14.0 ou supérieure** est nécessaire lorsqu'une dépendance doit être compilée.
Après l'installation, arrêter les services en cours et rouvrir le terminal avant de relancer
`uv sync --all-packages`.

**Linux.** Installer les outils de compilation C et C++ et `make`. Sur Debian ou Ubuntu :

```bash
sudo apt update
sudo apt install build-essential
```

Sur les autres distributions, utiliser le gestionnaire de paquets pour installer les outils équivalents.
Si une dépendance géospatiale doit être compilée depuis les sources, elle peut aussi nécessiter les
bibliothèques de développement et les versions compatibles indiquées dans sa documentation, par
exemple [GDAL pour Rasterio](https://rasterio.readthedocs.io/en/stable/installation.html) ou
[PROJ pour pyproj](https://pyproj4.github.io/pyproj/stable/installation.html).

## Installation

Depuis la racine du dépôt :

```text
git lfs pull                     # récupère les scénarios (~150 Mo chacun)
uv sync --all-packages           # dépendances Python de tous les services
cd frontend; npm install; cd ..  # dépendances de l'interface
```

## Lancement

```text
uv run python scripts/run_services.py
```

Le script, multiplateforme, prépare les scénarios puis démarre les trois briques :

| Brique | Adresse |
|---|---|
| Application | <http://localhost:5173> |
| API des scénarios (routing) | <http://localhost:8001/docs> |
| API des indicateurs (safety) | <http://localhost:8002/docs> |

Ouvrez <http://localhost:5173>. `Ctrl+C` arrête l'ensemble.

!!! tip "Premier lancement"
    Au premier lancement, la préparation des scénarios prend environ 100 secondes (voir
    [Données et préparation](../architecture/donnees.md)). Les lancements suivants sont immédiats.

## Sans backend

Pour une démonstration sans services Python, l'interface peut fonctionner avec des données simulées :

```text
cd frontend; npm run dev
```

puis ouvrir <http://localhost:5173/?source=mock&safetySource=mock>. Un badge « simulé » le signale à
l'écran. Voir [Paramètres et performances](parametres.md).

## En cas de problème

| Symptôme | Cause probable | Solution |
|---|---|---|
| « Microsoft Visual C++ 14.0 or greater is required » | compilateur C++ absent sous Windows | installer les Microsoft C++ Build Tools ci-dessus, rouvrir le terminal puis relancer `uv sync --all-packages` |
| Erreur de compilation d'une dépendance sous Linux | outils de compilation ou bibliothèques de développement manquants | installer les outils ci-dessus ; consulter le message d'erreur et la documentation de la dépendance |
| Un service s'arrête au démarrage (`ImportError`) | environnement Python incomplet | arrêter les services puis `uv sync --all-packages` |
| « Port déjà utilisé » | une ancienne instance tourne encore | l'arrêter, ou `--only` pour ne lancer qu'une partie |
| Trajets en « non disponible » | service safety arrêté | relancer `run_services.py` |
| Liste de scénarios vide ou erreur 503 | fichiers LFS non téléchargés | `git lfs pull` |
| Animation saccadée | pas d'accélération matérielle | voir [Paramètres et performances](parametres.md) |
