# Changelog

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
