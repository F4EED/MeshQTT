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
| Broker | `192.168.1.66` | Adresse du broker (Pi Mosquitto LAN) |
| Port | `1883` | `8883` si TLS |
| Username / Password | (vide en local) | Auth broker si configurée |
| Root topic | `msh/EU_868` | Préfixe des topics Meshtastic (réseau **Gaulix**, crossband) |

Le root topic **Gaulix** est `msh/EU_868` — **identique quelle que soit la bande** du nœud (433 ou 868 MHz) : le crossband est assuré par le serveur MQTT.

Le **firmware Meshtastic** ajoute ensuite un segment fixe `/2/` dans les topics MQTT :

| Mode radio | Topic complet (ex. canal D_Ligerien) |
|------------|--------------------------------------|
| **JSON enabled** (uplink courant) | `msh/EU_868/2/json/D_Ligerien/!node` |
| **Protobuf** (JSON désactivé) | `msh/EU_868/2/e/D_Ligerien/!node` |

MeshQTT s’abonne aux deux formats (`2/json/` et `2/e/`) via **wildcard** `{root}2/e/#` et `{root}2/json/#` : **tous les canaux** remontés par la gateway sont reçus, pas seulement le canal d’envoi actif.

Exemples d’abonnements MeshQTT :

- `msh/EU_868/2/json/D_Ligerien/#`
- `msh/EU_868/2/e/Fr_Balise/#`

Publication MeshQTT (downlink protobuf) : `{root}/2/e/{canal}/{node_id}` — avec le **même root** que la radio.

Si le root se termine par `/` (ex. `msh/EU_868/`), le firmware Meshtastic produit un **double slash** : `msh/EU_868//2/e/Fr_Balise/!node`. MeshQTT suit désormais la même règle (concaténation `root + "/2/e/"`).

Sur la radio, root topic **`msh/EU_868`** sans slash final évite le double slash ; les deux formats restent supportés à la réception.

Guide pas à pas pour une **radio gateway** : [mqtt-gateway.md](mqtt-gateway.md).

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

> **Desactive pour le moment** : UI, API `/api/inforoute42` et couche carte commentees dans le code. Voir `scripts/comment_inforoute.py` et les blocs `Info Routes 42 — desactive` dans les sources.

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
