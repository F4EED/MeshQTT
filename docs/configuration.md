# Configuration

## Fichiers de configuration

| Emplacement | Rôle |
|-------------|------|
| `data/settings.json` | Config serveur (MQTT, Meshtastic, thème) |
| `localStorage` (`meshqtt-settings`) | Copie navigateur, mode offline-first |
| `localStorage` (`meshqtt-presets`, `meshqtt-preset-categories`) | Messages prédéfinis et rubriques (compléments locaux) |
| `data/presets.json` | Messages prédéfinis **embarqués** (visibles à chaque ouverture) |

Au démarrage : si **localStorage** est vide, l’interface charge `data/settings.json` via `/api/settings` (canaux Meshtastic embarqués inclus). Sinon, la copie locale est utilisée et resynchronisée vers le serveur.

## MQTT

| Paramètre | Exemple | Description |
|-----------|---------|-------------|
| Broker | `127.0.0.1` | Adresse du broker |
| Port | `1883` | `8883` si TLS |
| Username / Password | (vide en local) | Auth broker si configurée |
| Root topic | `msh/EU_868/2/e/` | Préfixe des topics Meshtastic |

Le root topic doit correspondre à votre région / bande (ex. `msh/EU/433/2/e/`).

Guide pas à pas pour une **radio gateway** : [mqtt-gateway.md](mqtt-gateway.md).

Topics utilisés :

- Abonnement : `{root_topic}{nom_canal}/#`
- Publication : `{root_topic}{nom_canal}/{node_id}`

## Meshtastic — 8 canaux (indices 0–7)

Chaque canal :

| Champ | Description |
|-------|-------------|
| `role` | `PRINCIPAL`, `SECONDAIRE` ou `DESACTIVE` (canal actif sur MQTT si ≠ DESACTIVE) |
| `name` | Nom du canal (ex. `D_Ligerien`, `Fr_BlaBla`) |
| `key` | Clé PSK base64 (`AQ==` = pas de chiffrement effectif) |
| `enabled` | Dérivé automatiquement : `true` si rôle ≠ `DESACTIVE` |

Exemple (`data/settings.json`) :

```json
{
  "name": "D_Ligerien",
  "key": "",
  "role": "SECONDAIRE",
  "enabled": true
}
```

### Canal actif

`active_channel` : index du canal par défaut pour l’envoi groupe (0–7).

### Identité du nœud virtuel

| Champ | Description |
|-------|-------------|
| `short_name` | 4 caractères max (affiché sur le mesh) |
| `long_name` | Nom complet |
| `node_id` | ID numérique ; bouton « Proposer » ou laisser générer à la connexion |

MeshQTT simule un nœud MQTT sans radio ; les autres gateways relaient les paquets.

## Info Routes 42 — canaux par défaut

| Action | Canal |
|--------|-------|
| Texte signalement | **D_Ligerien** (trouvé par nom dans la config) |
| Waypoint (repère carte) | **Canal 0** |

Configurable dans le code : `INFOROUTE_DEFAULT_CHANNEL`, `INFOROUTE_WAYPOINT_CHANNEL` (`app/static/app.js`).

## Thème interface

`ui.theme` : `dark` ou `light`. Basculable via le bouton ☾ en en-tête.

## Zone Info Routes 42

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| `ui.inforoute_enabled` | `true` | Affiche la zone « Remontée Info Routes 42 » et les signalements sur la carte |

Case à cocher **Info Routes 42** dans l’en-tête. Si désactivé :

- le panneau **Remontée Info Routes 42** est **masqué** ;
- aucune actualisation automatique Inforoute (pas d’appel Internet) ;
- la **carte** reste accessible : fond OSM seul, sans marqueurs Inforoute.

Si activé : panneau visible, signalements Inforoute sur la carte (actualisation auto 30 min).

Réglage persisté dans `localStorage` et `data/settings.json`.

## Migration automatique

- Ancien broker `mqtt.meshtastic.org` → `127.0.0.1` (settings + localStorage)
- Ancien format canal unique → 8 slots canaux

## Sécurité

- Ne pas committer de mots de passe MQTT dans git
- `data/settings.json` peut contenir des clés de canal — rester en local
- Seule **Info Routes 42** appelle Internet (voir [inforoute42.md](inforoute42.md))
