# Changelog

## 1.0.0 — 2026-11-13

Version **Noctambulle** intégrant les contributions de l'équipe setec.
Ce numéro de version ne change pas le statut de prototype de hackathon.

### Fonctionnalités

- Trois indicateurs contextuels : éclairage nocturne et densité de population sur les portions
  à pied/en attente, fréquentation estimée sur les arcs en transport collectif.
- Fréquentation issue du CSV par arc, à partir de `estimated_validations_per_service_adjusted`,
  et intégration du raster de présence humaine `PresenceHum_IDF_OK.tif`.
- Score global du trajet calculé par moyenne pondérée des moyennes temporelles de chaque indicateur.
  Les poids sont configurables dans l'API et dans le panneau de l'interface :
  rouge/faible, gris/normal, vert/fort, puis normalisation pour totaliser 100 %.
- Couleur des bulles d'arrivée fondée sur le score global pondéré ; les couleurs locales restent
  indépendantes des préférences. La taille des bulles suit la population de destination disponible.
- Ambiance sonore activée par défaut, démarrant à la première interaction si le navigateur bloque
  la lecture automatique, sans annuler une désactivation explicite.
- Nom Noctambulle harmonisé dans l'interface, les titres et les métadonnées de l'application.

### Documentation et lancement

- Documentation technique et utilisateur actualisée, avec captures de l'interface, provenance
  des données et contributions métier de l'équipe.
- Badge vers la [documentation publiée](https://setec-labs.github.io/hackaviz-2026/) dans le README.
- Installation séparée du lancement ; commande unique mise en avant :
  `uv run python scripts/run_services.py`.
- Versions des packages alignées sur `1.0.0`. Les noms techniques des packages Python et les
  contrats publics restent inchangés.

### Limites connues

- Les indicateurs ne mesurent ni un danger objectif ni la présence nocturne ou l'occupation
  effectivement observées. Les absences de données sont signalées, pas remplacées par une valeur neutre.
- Les scénarios restent précalculés, les horaires théoriques et les destinations représentées
  par les mairies ; le rapport par scénario n'est pas implémenté.
- L'application fonctionne localement. GitHub Pages publie uniquement la documentation ;
  les données volumineuses nécessitent Git LFS et le fond de carte un accès Internet.

## 0.01 — 2026-11-12

Première version du prototype réalisé par l'équipe setec pour le
[Hackaviz Mobilités 2026](https://github.com/hackathons-mobilites/hackaviz_2026).

### Fonctionnalités

- Carte interactive des trajets nocturnes en Île-de-France, avec sélection d'un scénario de départ,
  animation des trajets, réglages de vitesse et son d'arrivée.
- Bulles d'arrivée dimensionnées selon la population de destination et colorées selon l'indice des
  dix minutes les plus défavorables du trajet, consécutives ou non. Les trajets de plus de deux
  heures sont affichés en couleur neutre.
- API routing servant des scénarios précalculés et commande reproductible d'optimisation de leurs
  fichiers de trajets.
- API safety exposant un indicateur d'éclairage normalisé à partir d'un raster en échelle
  logarithmique. L'indice est évalué sur les portions à pied et en attente ; les portions en
  véhicule reçoivent provisoirement la valeur neutre 0,5.
- Script multiplateforme de démarrage local des services et du frontend.

### Documentation et qualité

- Guide utilisateur, choix métier et architecture documentés avec Zensical.
- Documentation technique du code, contrats d'API typés et tests des services et du frontend.
- Workflow GitHub Actions pour les tests et la publication de la documentation sur GitHub Pages :
  version stable à la racine et version de développement sous `/dev/`.

### Limites connues

- Ce prototype de hackathon n'est ni un outil de planification ni une mesure objective de sécurité :
  un faible éclairage ou un indice défavorable ne prouve pas qu'un lieu est dangereux.
- Les horaires sont théoriques, les destinations sont représentées par les mairies et l'éclairage
  constitue le seul indicateur actuellement disponible.
- Le rapport par scénario n'est pas encore implémenté.
- L'application est prévue pour un fonctionnement local ; le workflow de déploiement concerne
  uniquement la documentation. Les données volumineuses nécessitent Git LFS.
