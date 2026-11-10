# Frontend

Cette brique contient l'interface de visualisation du projet Hackaviz Mobilités 2026 : une cartographie
interactive des trajets de nuit en Île-de-France, animés dans le temps et colorés selon un indicateur lié au
sentiment de sécurité.

Le prototype actuel fonctionne **sans backend** : les deux futures API FastAPI (trajets et indice) sont
remplacées par des données simulées.

> L'indice affiché est un **indicateur**. Il ne mesure pas objectivement le danger d'un lieu. Les valeurs
> simulées sont synthétiques et sans lien avec des lieux réels.

## Stack

| Rôle | Outil |
|---|---|
| Interface | React 19 + TypeScript |
| Build / serveur de dev | Vite |
| Carte | MapLibre GL JS (fond vectoriel sombre CARTO / OpenStreetMap, sans clé) |
| Couches de données (GPU) | deck.gl (`TripsLayer`, `PathLayer`, `ScatterplotLayer`) via `@deck.gl/mapbox` |
| Styles | Tailwind CSS 4 |
| Tests | Vitest |

## Installation

Prérequis : Node.js 20+ (npm est fourni avec Node).

uv gère les dépendances Python du monorepo mais pas les paquets JavaScript : les dépendances du frontend sont
donc gérées avec **npm**, dans ce dossier. Le fichier `package-lock.json` est versionné.

```powershell
cd frontend
npm install
```

Pour ajouter une bibliothèque JavaScript :

```powershell
npm install <librairie>          # dépendance d'exécution
npm install -D <librairie>       # dépendance de développement
```

Le `pyproject.toml` de cette brique est conservé pour l'intégration au workspace uv ; aucune dépendance
Python n'est nécessaire au frontend.

## Lancer le prototype

```powershell
cd frontend
npm run dev
```

Puis ouvrir <http://localhost:5173>. Le fond de carte nécessite un accès Internet ; en son absence, les
trajets restent affichés sur un fond uni.

Autres commandes :

```powershell
npm run typecheck   # vérification TypeScript
npm test            # tests unitaires (Vitest)
npm run build       # build de production dans dist/
npm run preview     # sert le build de production
```

### Paramètres de test (URL)

| Paramètre | Effet | Exemple |
|---|---|---|
| `trips` | nombre de trajets simulés (0 à 20 000) | `?trips=3000` |
| `seed` | graine des données simulées | `?seed=7` |
| `latency` | latence simulée des API, en ms | `?latency=0` |
| `mockError` | simule la panne d'un service (`trips` ou `safety`) | `?mockError=safety` |

Le nombre de trajets par défaut peut aussi être défini avec `VITE_MOCK_TRIP_COUNT` (voir `.env.example`).

### Utilisation

- **Lecture / pause** : bouton principal ou touche Espace.
- **Recommencer** : revient au début de la timeline.
- **Timeline** : le curseur permet de se déplacer dans le temps simulé.
- **Vitesse** : définit combien de secondes réelles représente 1 heure simulée
  (temps réel = 3 600 s, normale = 60 s, rapide = 10 s, très rapide = 1 s). Modifiable pendant l'animation.
- **Clic sur la carte** : choisit un nouveau point de départ et recharge les trajets.
- **Survol** d'un trajet ou d'un point : infobulle avec le mode, les horaires et l'indicateur au point courant.

## Architecture

```text
frontend/
├── index.html
├── vite.config.ts
├── .env.example              # variables VITE_* (source de données, URL des API, volume du mock)
└── src/
    ├── main.tsx, App.tsx      # point d'entrée et assemblage de l'interface
    ├── config.ts              # configuration (.env + paramètres d'URL)
    ├── theme/palette.ts       # palette du projet (source TS) ; miroir Tailwind dans index.css
    ├── domain/                # types métier et lecture de l'indice (seuils, libellés, couleurs)
    ├── api/
    │   ├── contracts.ts       # contrats JSON attendus des API FastAPI (snake_case, provisoires)
    │   ├── validation.ts      # validation des réponses + conversion vers le domaine
    │   ├── clients.ts         # interfaces TripsClient / SafetyIndexClient
    │   ├── http/              # clients FastAPI (fetch)
    │   └── index.ts           # createDataClients : choix mock / API
    ├── mocks/                 # données simulées (trajets, champ d'indice, clients mock)
    ├── data/                  # chargement (états loading/error/success) et préparation pour le rendu
    ├── simulation/            # horloge de simulation commune + préréglages de vitesse
    ├── layers/                # couches deck.gl, positions courantes, infobulle
    ├── map/                   # carte MapLibre + overlay deck.gl, thème du fond de carte
    └── components/            # composants UI (panneau de contrôle, légende, états)
```

### Flux de données

```text
TripsClient.fetchTrips(origin) ──► Trip[] ──┐
                                            ├─► prepareDataset ─► RenderDataset ─► couches deck.gl
SafetyIndexClient.fetchSafetyIndices(pts) ──┘                                         ▲
                                                           SimulationClock.onFrame ───┘
```

- Si le service **trajets** échoue, un message d'erreur avec bouton « Réessayer » est affiché.
- Si le service **indice** échoue, les trajets restent affichés et l'indicateur est signalé
  « non disponible » (aucune valeur n'est inventée).

### Horloge et performance

- Une **seule horloge** (`src/simulation/SimulationClock.ts`) et une seule boucle `requestAnimationFrame`
  pilotent toutes les animations : aucun timer par trajet, tous les trajets restent synchronisés.
- À chaque image, l'horloge appelle directement `overlay.setProps({ layers })` : **aucun rendu React par
  image**. L'interface React n'est notifiée qu'environ 10 fois par seconde (heure affichée, compteur).
- L'animation des traînées est faite sur GPU par `TripsLayer` (`currentTime`).
- Les positions courantes des trajets sont calculées dans des tableaux typés préalloués et transmises à
  deck.gl en attributs binaires (pas d'objet ni de composant par point).
- Testé visuellement avec `?trips=3000`.

### Lecture de l'indice

L'indice est normalisé entre 0 et 1 (1 = contexte le plus favorable). Sa représentation est définie dans
`src/domain/safetyLevels.ts` : dégradé continu cyan → ambre → orange de la palette, et quatre niveaux
libellés pour la légende. La taille du point de tête augmente avec le niveau de vigilance afin que la
couleur ne soit pas le seul vecteur d'information. Ces seuils sont un choix de visualisation : le calcul de
l'indice appartient au service `services/safety`.

## Données simulées

Toutes les données simulées sont dans [`src/mocks/`](src/mocks/) :

- `tripGenerator.ts` : génère une réponse au format de l'API trajets (trajets autour du point de départ vers
  des pôles d'Île-de-France, modes et vitesses variés, départs étalés à partir du 13/11/2026 22:00) ;
- `safetyField.ts` : champ synthétique d'indice (zones aléatoires, quelques zones sans donnée) ;
- `mockClients.ts` : `MockTripsClient` et `MockSafetyIndexClient`, qui implémentent les mêmes interfaces que
  les clients HTTP et passent par le **même validateur** que les réponses réelles.

Les données sont déterministes pour une graine donnée et ne sont jamais codées dans les composants React.

## Remplacer les mocks par les API FastAPI

1. Implémenter côté services les routes attendues (contrats dans `src/api/contracts.ts`, **provisoires**) :
   - `GET {VITE_TRIPS_API_URL}/trips?latitude=..&longitude=..` → `TripsResponseDto`
   - `POST {VITE_SAFETY_API_URL}/safety-index` avec `{ "points": [...] }` → `SafetyIndexResponseDto`
     (indices dans l'ordre des points, `value` entre 0 et 1 ou `null`).
2. Aligner ces contrats avec les modèles Pydantic partagés de `src/hackaviz_2026/` et ajuster
   `contracts.ts`, `validation.ts` et, si besoin, les routes dans `src/api/http/fastApiClients.ts`.
3. Créer un fichier `frontend/.env.local` :

   ```text
   VITE_DATA_SOURCE=api
   VITE_TRIPS_API_URL=http://localhost:8001
   VITE_SAFETY_API_URL=http://localhost:8002
   ```

   (ou ajouter `?source=api` à l'URL). Activer CORS sur les services FastAPI pour l'origine du frontend.
4. Aucun composant, couche ou hook n'a besoin d'être modifié : le choix se fait uniquement dans
   `src/api/index.ts` (`createDataClients`).

## Où travailler ?

Le code spécifique à l'interface doit rester dans cette brique. Le code ou les modèles nécessaires à
plusieurs briques ont vocation à être placés dans le package commun `src/hackaviz_2026/`.

## Avant de pousser vos modifications

Exécuter `npm run typecheck`, `npm test`, vérifier que `npm run dev` démarre correctement, puis pousser sur
votre branche personnelle. La Pull Request devra cibler la branche `develop`.
