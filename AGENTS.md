# Instructions pour les agents

## Avant toute modification

1. Lire `.github/copilot-instructions.md`.
2. Identifier la brique concernee.
3. Lire le README et le fichier `AGENTS.md` les plus proches.
4. Examiner les modeles partages dans `src/hackaviz_2026/`.
5. Verifier les tests existants avant de modifier le comportement.

## Methode de travail

Avant d'ecrire du code :

- reformuler brievement l'objectif technique ;
- identifier les fichiers concernes ;
- rechercher une implementation existante reutilisable ;
- eviter les modifications hors perimetre.

Pendant la modification :

- conserver l'architecture existante ;
- produire la modification minimale necessaire ;
- ne pas refactoriser du code sans rapport direct avec la demande ;
- preserver les interfaces publiques sauf demande explicite ;
- utiliser les modeles Pydantic partages pour les echanges entre briques.

Apres la modification :

- executer les tests pertinents ;
- verifier le formatage et les types si les outils sont configures ;
- expliquer les fichiers modifies ;
- signaler les hypotheses, limites et risques restants.

## Commandes

Le projet utilise uv.

Utiliser :

```text
uv sync
uv run <commande>
uv run --package <package> <commande>
uv add --package <package> <dependance>
```

Ne pas utiliser Poetry ou pip pour modifier l'environnement du projet.

## Limites

L'agent ne doit pas :

- introduire une nouvelle technologie sans justification ;
- deplacer massivement les fichiers ;
- modifier les contrats partages sans verifier leurs consommateurs ;
- ajouter une dependance pour quelques lignes de code simples si la bibliotheque standard suffit ;
- presenter un indicateur comme une preuve objective de danger ;
- ajouter des secrets, jetons ou donnees personnelles au repository.
