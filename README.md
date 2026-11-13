# Trajets de nuit · Île-de-France

**Comment se vivent les trajets de nuit en transports en commun en Île-de-France ?** Cette
visualisation cartographique anime les trajets depuis différents lieux et heures de départ, et met en
regard leur durée, les portions à pied ou en attente, l'éclairage nocturne et la fréquentation estimée.

> **Prototype de hackathon.** Réalisé en deux semaines par l'équipe setec pour le
> [Hackaviz Mobilités 2026](https://github.com/hackathons-mobilites/hackaviz_2026), organisé par
> Île-de-France Mobilités. Ce projet est une démonstration de concept, pas un outil de planification ni
> une mesure objective de la sécurité. Un indice défavorable ou un faible éclairage ne constitue pas une
> preuve qu'un lieu est dangereux.

![Carte animée des trajets de nuit au départ de Pigalle](docs/assets/carte.png)

## Présentation du projet

La nuit, connaître la durée d'un trajet ne suffit pas toujours à comprendre l'expérience d'une personne.
Un long temps d'attente, une marche de correspondance ou un trajet qui n'est pas réalisable avant le
matin peuvent compter autant que le temps passé dans les transports.

Le projet permet d'explorer ces dimensions sur une carte animée de l'Île-de-France. Il s'adresse aux
personnes qui souhaitent visualiser l'accessibilité nocturne du territoire, ainsi qu'aux équipes qui
réfléchissent à l'offre de transport et à son environnement.

### Le problème et la proposition de valeur

Les horaires et les itinéraires indiquent où et quand l'on peut se déplacer, mais ne décrivent pas à eux
seuls l'environnement vécu pendant les portions à pied et les attentes. La carte rapproche ces
informations sans prétendre prédire le ressenti individuel ni mesurer objectivement le danger.

### La solution

L'application présente plusieurs scénarios de départ nocturnes. Pour chaque scénario, elle anime les
trajets calculés vers les mairies des communes d'Île-de-France (Paris est représentée par ses
arrondissements). Les bulles d'arrivée représentent la population de la destination ; leur couleur
résume un score global pondéré du trajet, configurable dans l'interface.

Les trajets de plus de deux heures sont affichés en gris comme peu plausibles : une personne aurait
probablement choisi un autre mode de déplacement. Les indices locaux utilisent l'éclairage nocturne
sur les portions de marche et d'attente, et la fréquentation estimée sur les arcs en transport.
Ils sont normalisés entre 0 et 1, où 1 indique le contexte le plus favorable selon ces hypothèses.
Le score global combine les moyennes temporelles de ces deux indicateurs. Le panneau rouge/gris/vert
règle leur importance ; les poids totalisent 100 %. Une donnée manquante reste indisponible.

Les principales données mobilisées sont les horaires théoriques GTFS d'Île-de-France Mobilités, le réseau
piéton issu d'OpenStreetMap, un raster de luminosité nocturne et des données de population. Les scénarios
sont précalculés ; le frontend les consulte via l'API routing et demande les indices à l'API safety.

### Les problèmes surmontés et les enjeux en matière de données

Les scénarios de trajets bruts sont volumineux (environ 150 Mo chacun). Une commande reproductible les
simplifie en préservant les temps et les types de tronçons ; les fichiers utilisés par l'application font
environ 10 Mo. L'architecture sépare le calcul des trajets, l'évaluation de l'éclairage et la
visualisation pour permettre à l'équipe d'avancer sur ces briques en parallèle.

Le prototype met aussi en évidence des limites des données et de leur interprétation : les horaires sont
théoriques, la mairie représente la commune plutôt que l'adresse réelle d'une personne, et l'éclairage
n'est qu'un facteur parmi d'autres. Pour de futurs projets, des données ouvertes et documentées sur les
correspondances piétonnes, les cheminements accessibles et l'état réel du service aideraient à décrire
plus fidèlement les déplacements nocturnes. Des indicateurs complémentaires devraient être contextualisés
et validés avec les personnes concernées.

### Et la suite ?

Les prochaines étapes pourraient être :

- compléter l'indice avec d'autres facteurs de l'environnement nocturne, sans les confondre avec une
  mesure objective de sécurité ;
- confronter les estimations de fréquentation aux données observées et aux ressentis ;
- proposer des alternatives aux trajets jugés peu plausibles ;
- implémenter le rapport par scénario et valider les choix de visualisation avec des usagers ;
- documenter les données et hypothèses avec les partenaires, puis mesurer les performances sur des
  machines modestes.

## Installation et utilisation

### Prérequis

- [Git](https://git-scm.com/) et [Git LFS](https://git-lfs.com/) pour les fichiers de données volumineux ;
- [uv](https://docs.astral.sh/uv/) et Python 3.14 ;
- Node.js et npm pour le frontend.

### Démarrer l'application

```text
git clone https://github.com/setec-labs/hackaviz-2026.git
cd hackaviz-2026
git lfs install
git lfs pull
uv sync --all-packages
cd frontend
npm ci
cd ..
uv run python scripts/run_services.py
```

Ouvrir ensuite <http://localhost:5173>. Les API sont également disponibles sur
<http://localhost:8001/docs> (routing) et <http://localhost:8002/docs> (safety). Arrêter les services
avec `Ctrl+C`.

Le guide d'installation complet, les conseils de dépannage et le mode de démonstration sans backend
sont dans [la documentation utilisateur](docs/utilisateur/index.md). Pour les commandes de tests et de
développement, consulter [CONTRIBUTING.md](CONTRIBUTING.md).

## Documentation

La documentation couvre le [guide utilisateur](docs/utilisateur/index.md), les
[choix métier](docs/metier/index.md), les [limites connues](docs/metier/limites.md) et
l'[architecture](docs/architecture/index.md). Elle est construite avec
[Zensical](https://zensical.org/) :

```text
uv run zensical serve
uv run zensical build
```

## Licence

Le code et la documentation sont distribués sous licence [MIT](LICENSE).
