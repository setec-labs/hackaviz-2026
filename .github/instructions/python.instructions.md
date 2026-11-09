---
applyTo: "**/*.py"
---

# Instructions Python

- Utiliser les annotations de type.
- Utiliser Pydantic pour les contrats d'entree et de sortie partages.
- Preferer `pathlib` aux manipulations de chemins sous forme de chaines.
- Utiliser des exceptions explicites.
- Ne pas capturer `Exception` sans traitement ou journalisation approprie.
- Eviter les variables globales mutables.
- Ajouter ou adapter les tests pour les comportements publics modifies.
- Utiliser uv pour gerer les dependances.
- Ne pas utiliser `pip install` pour ajouter une dependance au projet.
