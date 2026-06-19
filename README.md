# MeshQTT

Client Meshtastic **nodeless** (sans radio LoRa) accessible depuis un navigateur, conçu pour la **gestion de crise** sur réseau mesh via MQTT.

MeshQTT simule un nœud Meshtastic côté PC : il publie et reçoit des messages protobuf sur un broker MQTT, comme une gateway radio, mais sans matériel Meshtastic branché à la machine.

---

## Origines

MeshQTT est une **adaptation web** du projet [**Connect**](https://github.com/pdxlocations/connect) (*A Nodeless MQTT Client for Meshtastic*), créé par [**pdxlocations**](https://github.com/pdxlocations).

| | |
|---|---|
| **Projet d’origine** | [github.com/pdxlocations/connect](https://github.com/pdxlocations/connect) |
| **Auteur d’origine** | [pdxlocations](https://github.com/pdxlocations) |
| **Concept repris** | Pont MQTT Meshtastic sans nœud radio (protobuf, canaux, chiffrement PSK) |

À partir de Connect (client Python + Tkinter), MeshQTT ajoute une interface **navigateur** orientée **gestion de crise** (Loire) :

- Serveur **FastAPI** + frontend **HTML/CSS/JS** vanilla
- **8 canaux** Meshtastic configurables (rôles PRINCIPAL / SECONDAIRE / DESACTIVE)
- Messages **prédéfinis** par rubriques (embarqués + localStorage)
- Clavier d’envoi **groupe** et **direct**
- Intégration **Info Routes 42** (bulletin et signalements routiers)
- **Carte Leaflet** et envoi de **waypoints** Meshtastic
- Broker **Mosquitto** local via Docker

Remerciements également à la chaîne d’inspiration citée par Connect ([meshtastic-mqtt-client](https://github.com/arankwende/meshtastic-mqtt-client), [meshtastic-mqtt](https://github.com/joshpirihi/meshtastic-mqtt)) et à l’écosystème [Meshtastic](https://meshtastic.org).

Détails : [docs/origines.md](docs/origines.md)

---

## Architecture

```
Radio Meshtastic (gateway)  ←→  mesh LoRa  ←→  autres nœuds
         ↕ MQTT (LAN)
    Mosquitto (PC, :1883)
         ↕ MQTT
   MeshQTT (navigateur — nœud virtuel)
```

- **MeshQTT** se connecte au broker en `127.0.0.1:1883` (depuis le PC).
- La **radio gateway** se connecte à l’**IP LAN du PC** (ex. `192.168.1.x:1883`) — pas `127.0.0.1`.
- Les deux partagent le **même root topic** (ex. `msh/EU_868/2/e/`) et les **mêmes noms/clés de canaux**.

Guide gateway radio : [docs/mqtt-gateway.md](docs/mqtt-gateway.md)

---

## Fonctionnalités

| Domaine | Description |
|---------|-------------|
| **MQTT** | Connexion broker local ou distant, abonnement multi-canaux |
| **Messages** | Fil temps réel (WebSocket), déchiffrement PSK |
| **Nœuds** | Liste des nœuds visibles sur le mesh |
| **Canaux** | 8 emplacements (0–7), clés PSK, canal d’envoi par défaut |
| **Prédéfinis** | Rubriques dynamiques (Pompier, Secours, Crise…), intégration dans `data/presets.json` |
| **Clavier** | Envoi broadcast ou direct (canal 0) |
| **Info Routes 42** | Bulletin officiel Loire, remontée mesh, waypoints |
| **Carte** | Page `/map` (Leaflet, fond OSM) |
| **Interface** | Thème jour / nuit, config persistée |

---

## Démarrage rapide

### Prérequis

- Python **3.11+**
- **Docker** (Mosquitto local recommandé)
- Navigateur moderne (Chrome, Firefox, Edge)

### Installation

```powershell
git clone https://github.com/F4EED/MeshQTT.git
cd MeshQTT

python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt

docker compose up -d
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Ouvrir [http://127.0.0.1:8080](http://127.0.0.1:8080)

### Premier usage

1. **MQTT** → broker `127.0.0.1`, port `1883`, root topic adapté à votre région (ex. `msh/EU_868/2/e/`)
2. **Meshtastic** → canaux, nom court, ID nœud
3. **Connecter**
4. Configurer le **module MQTT** de la radio gateway vers l’IP LAN du PC ([guide](docs/mqtt-gateway.md))

---

## Configuration

| Fichier / emplacement | Rôle |
|-----------------------|------|
| `data/settings.json` | Config embarquée (MQTT, canaux, UI) |
| `data/presets.json` | Messages prédéfinis embarqués |
| `localStorage` | Copie navigateur (offline-first) |
| `docker/mosquitto/` | Config broker local |

Au premier démarrage sans cache navigateur, la config est chargée depuis `data/settings.json`.

Documentation complète : [docs/configuration.md](docs/configuration.md)

---

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Backend | FastAPI, uvicorn |
| MQTT | paho-mqtt, protobuf Meshtastic |
| Crypto | AES-CTR (`mesh_crypto.py`) |
| Frontend | HTML, CSS, JavaScript vanilla |
| Broker | eclipse-mosquitto:2 (Docker) |
| Carte | Leaflet + OpenStreetMap |

---

## Documentation

| Document | Contenu |
|----------|---------|
| [docs/origines.md](docs/origines.md) | Historique Connect → MeshQTT |
| [docs/installation.md](docs/installation.md) | Installation détaillée |
| [docs/configuration.md](docs/configuration.md) | MQTT, canaux, settings |
| [docs/mqtt-gateway.md](docs/mqtt-gateway.md) | Brancher une radio Meshtastic |
| [docs/utilisation.md](docs/utilisation.md) | Interface web |
| [docs/inforoute42.md](docs/inforoute42.md) | Info Routes 42 |
| [docs/cartographie.md](docs/cartographie.md) | Carte Leaflet |
| [docs/depannage.md](docs/depannage.md) | Dépannage |
| [docs/architecture.md](docs/architecture.md) | API, protocole, structure code |

---

## Crédits

- [**Connect**](https://github.com/pdxlocations/connect) — [pdxlocations](https://github.com/pdxlocations) — base du client MQTT nodeless Meshtastic
- [**Meshtastic**](https://meshtastic.org) — protocole et écosystème mesh

---

## Licence

MIT License — voir [LICENSE](LICENSE).  
Usage orienté gestion de crise ; vérifiez aussi la licence de [Connect](https://github.com/pdxlocations/connect) pour le code d’origine.
