# Info Routes 42

Intégration du bulletin officiel du [Conseil départemental de la Loire](https://www.inforoute42.fr/) pour la remontée mesh en gestion de crise.

## Source des données

| Flux | URL | Contenu |
|------|-----|---------|
| Page d’accueil | `inforoute42.fr` | Teaser, bulletin HTML |
| Repli | `route.php?type=config` | Bulletin XML |
| Signalements | `route.php?type=repere` | Accidents, travaux, gravillonnage… |
| Déviations | `route.php?type=barreau` | Tronçons / déviations |

API locale : `GET /api/inforoute42` (proxy serveur, seul accès Internet).

## Affichage

### Bulletin général

- Date de mise à jour du site
- Teaser + liste à puces
- Compteur : **mots · caractères · octets UTF-8**

### Signalements par catégorie

Catégories (comme le site) : Accident, Danger, Travaux, Gravillonnage, Autres, Déviation.

**Rubriques vides (0 signalement) masquées.**

### Coordonnées (commentaire sous chaque signalement)

Pour chaque `<repere>` / `<barreau>` :

```
// point_latlng : 45.73…;3.83…
// point_xy : 88.154;227.974
// latitude / longitude (XML) : …
// latitude / longitude (transform. xy → WGS84) : …
// formule : lat = … ; lon = …
```

Les coordonnées **ne sont pas** incluses dans le message texte mesh.

## Envoi mesh

### Message texte

Contenu : titre + description + période (max 200 octets UTF-8).

Canal par défaut : **D_Ligerien**.

### Waypoint (repère carte)

Protocole Meshtastic `WAYPOINT_APP` :

- `latitude_i` / `longitude_i` = degrés × 10⁷
- Nom = titre (30 car. max)
- Description (100 car. max)
- Icône 📍 (`128205`)
- Expiration : +24 h
- Canal : **0**

API : `POST /api/waypoint`

```json
{
  "latitude": 45.731903,
  "longitude": 3.838576,
  "name": "Début de gravillonnage - RD1089",
  "description": "Présence de gravillons…",
  "channel": 0
}
```

Les repères apparaissent sur la **carte** des clients Meshtastic (Android/iOS/Web), pas dans le fil texte.

## Transformation point_xy → WGS84

Si besoin de recalcul (repère interne carte Flash) :

```
lat = -6.422e-05·x - 0.00245244·y + 46.296656
lon =  0.00175586·x - 4.598e-05·y + 3.694272
```

Priorité : toujours utiliser `point_latlng` du XML quand disponible.

## Zone « Remontée mesh »

Texte éditable + choix de canal + **Remonter sur le mesh** (envoi manuel du textarea).

## Téléphone Info routes

Affiché en bas : **04 77 34 46 06**

## Fichier code

- Backend : `app/inforoute42.py`
- Frontend : `app/static/app.js` (render, envoi, auto-refresh 30 min)
