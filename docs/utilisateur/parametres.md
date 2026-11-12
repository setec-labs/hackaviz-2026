# Paramètres et performances

## Paramètres d'URL

Des paramètres ajoutés à l'adresse de l'application permettent de tester sans backend ou de changer le
volume de données :

| Paramètre | Effet | Exemple |
|---|---|---|
| `source` | scénarios : `api` (défaut) ou `mock` (simulés) | `?source=mock` |
| `safetySource` | indice : `api` (défaut) ou `mock` (simulé) | `?safetySource=mock` |
| `trips` | nombre de trajets par scénario simulé (0 à 20 000) | `?trips=3000` |
| `seed` | graine des données simulées | `?seed=7` |
| `latency` | latence simulée des API, en ms | `?latency=0` |
| `mockError` | simule la panne d'un service : `trips` ou `safety` | `?mockError=safety` |

Les paramètres se combinent : `?source=mock&safetySource=mock&trips=300`.

!!! warning "Données simulées"
    Les données `mock` sont synthétiques et sans lien avec des lieux réels. Un badge le signale à l'écran.

## Configuration recommandée

L'animation est dessinée par la **carte graphique** (WebGL). La fluidité dépend donc surtout du GPU et de
l'accélération matérielle du navigateur ; le processeur n'intervient vraiment qu'au chargement d'un
scénario.

| Élément | Recommandation |
|---|---|
| Navigateur | Chrome, Edge ou Firefox récent, accélération matérielle activée |
| Carte graphique | une puce intégrée récente (Intel Iris, Apple M) suffit a priori |
| Mémoire | 8 Go |
| Réseau | Internet pour le fond de carte |

Pour vérifier l'accélération matérielle, ouvrir `chrome://gpu` ou `edge://gpu` : la ligne « WebGL2 » doit
indiquer « Hardware accelerated ».

## Si l'animation est saccadée

1. Vérifier l'accélération matérielle (voir ci-dessus).
2. Réduire la fenêtre ou le zoom du navigateur : moins de pixels à dessiner.
3. Simplifier davantage les scénarios, au prix d'un tracé moins précis :

    ```powershell
    uv run --package routing optimize-scenarios --force --tolerance-m 20
    ```

    Environ 10 % des points sont conservés, contre 14 % avec la valeur par défaut de 10 m.

!!! note
    Ces recommandations découlent de l'architecture ; elles n'ont pas été mesurées sur une machine
    modeste.
