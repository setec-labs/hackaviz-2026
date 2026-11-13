# Limites connues

!!! warning "Rappel"
    Ce prototype a été réalisé en deux semaines pour le
    [Hackaviz Mobilités 2026](https://github.com/hackathons-mobilites/hackaviz_2026). Les limites
    ci-dessous sont assumées et listées pour être lues avec les résultats.

## Données et indicateurs

- **Trois indicateurs seulement.** Éclairage et densité à pied/en attente, fréquentation estimée à bord :
  commerces ouverts, personnel et aménagement des arrêts ne sont pas pris en compte.
- **Fréquentation approximative.** Les validations estimées par service ne mesurent pas l'occupation.
  Elles utilisent des imputations et des ratios de taille de véhicule. Associer une fréquentation plus
  élevée à un contexte plus favorable est une hypothèse, non une preuve de sécurité.
- **Unité de l'éclairage.** Le raster est en échelle logarithmique de 0 à 100, mais son unité physique
  n'est pas documentée.
- **Densité et présence nocturne.** Le raster de densité est un indice préparé de 0 à 100,
  inversé selon la convention fournie. Sa construction amont reste à documenter ;
  il ne mesure pas la présence humaine observée la nuit.
- **Horaires théoriques.** Les itinéraires utilisent les horaires GTFS prévus, pas les passages réels
  (retards, suppressions, travaux).
- **Une seule nuit.** Les scénarios portent sur la nuit du 7 au 8 novembre 2026.
- **Destination = mairie.** Chaque commune est représentée par sa mairie ; les trajets vers le reste de
  la commune peuvent être très différents.

## Modélisation

- **Seuils de visualisation.** Les 2 heures de plausibilité et les quatre niveaux de la légende sont des
  choix de représentation, non validés par une étude.
- **Trajets très longs.** La majorité des trajets calculés dépassent 2 heures, avec parfois des marches de
  plusieurs heures. Ils sont grisés plutôt que recalculés avec un autre mode (taxi, VTC, vélo).
- **Rapport par scénario.** La route `POST /report` (bilan par scénario) est définie mais pas implémentée :
  elle répond « non implémenté » (501).

## Technique

- **Pas de déploiement.** L'application est prévue pour fonctionner en local.
- **Performances non mesurées** sur une machine modeste : voir
  [Paramètres et performances](../utilisateur/parametres.md).
- **Données volumineuses.** Les scénarios bruts pèsent environ 150 Mo chacun ; une version allégée est
  générée automatiquement (voir [Données](../architecture/donnees.md)).

## Pistes pour la suite

- Ajouter des indicateurs (commerces ouverts la nuit, aménagement des arrêts) et valider les
  estimations de fréquentation avec des observations.
- Proposer une alternative chiffrée aux trajets de plus de 2 heures (taxi, vélo, VTC).
- Implémenter le rapport par scénario : personnes arrivées et anxiété par destination.
- Faire valider les seuils et la notion d'« anxiété des 10 pires minutes » par des usagers.
