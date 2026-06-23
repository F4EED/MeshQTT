# Cartographie

Carte **Leaflet** : fond OpenStreetMap ; couche **Info Routes 42** si activée dans les réglages.

## Accès

- Bouton **Carte** dans l’en-tête de la page principale (toujours visible)
- Ouvre une **nouvelle fenêtre** navigateur : [http://127.0.0.1:8080/map](http://127.0.0.1:8080/map)

## Positions Meshtastic

Les positions reçues via MQTT sont **conservées en mémoire** côté serveur (dernière position par nœud).

| Moment | Comportement |
|--------|----------------|
| Ouverture de `/map` | Chargement via `GET /api/positions`, puis marqueurs sur la carte |
| Carte déjà ouverte | WebSocket `/ws` — événement `type: position` à chaque réception MQTT |

- Un marqueur coloré par nœud (`from_id`), mis à jour à chaque nouvelle position
- Clic : nom court/long, canal, coordonnées, horodatage
- Légende : nombre de nœuds visibles
- Coordonnées `0, 0` ignorées (position invalide)

## Info Routes 42 sur la carte

Contrôlé par la case **Info Routes 42** (réglage `ui.inforoute_enabled`) :

| Case | Page principale | Carte |
|------|-----------------|-------|
| Cochée | Panneau Remontée visible | Marqueurs Inforoute + actualisation auto 30 min |
| Décochée | Panneau masqué | Fond OSM seul (pas d’appel Inforoute) |

La carte lit le réglage au chargement (`localStorage`) et se synchronise si vous changez la case (fenêtre ouverte) via `BroadcastChannel`.

## Offline / online

| Composant | Mode |
|-----------|------|
| `map.html`, `map.js`, `map.css` | **Local** (servis par MeshQTT) |
| `leaflet/` (JS + CSS) | **Local** (`app/static/leaflet/`) |
| Tuiles fond de carte (OpenStreetMap) | **En ligne** |
| Données signalements Inforoute | API locale → proxy Internet (si couche activée) |

Sans Internet : la carte s’affiche mais **sans fond** ; les marqueurs Inforoute nécessitent une actualisation réussie.

## Affichage (couche Inforoute)

- Vue initiale : **France + Corse** (centre ~46,5°N / 2,5°E, zoom 6)
- Marqueurs colorés par catégorie (Accident, Danger, Travaux, etc.)
- Clic sur un marqueur : popup titre, description, période
- Légende en bas à droite avec compteurs

## Actualisation Inoroute

- Automatique **toutes les 30 minutes** (si couche activée)
- Bouton **Actualiser Inforoute** manuel (masqué si couche désactivée)
- Si la page principale actualise Inforoute, la carte ouverte se **synchronise** via `BroadcastChannel`

## Fichiers

```
app/static/map.html
app/static/map.js
app/static/map.css
app/static/leaflet/     # bibliothèque embarquée
```

Route FastAPI : `GET /map`

## Évolutions prévues

- Données **Meshtastic** (nœuds, positions) sur la même carte
- Tuiles fond de carte **offline** (MBTiles ou cache local)
- Tracés polylignes pour déviations (barreaux)
