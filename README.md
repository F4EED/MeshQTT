# MeshQTT

```
  ███╗   ███╗ ███████╗ ███████╗ ██╗  ██╗      ██████╗  ████████╗ ████████╗
  ████╗ ████║ ██╔════╝ ██╔════╝ ██║  ██║     ██╔═══██╗ ╚══██╔══╝ ╚══██╔══╝
  ██╔████╔██║ █████╗   ███████╗ ███████║     ██║   ██║    ██║       ██║
  ██║╚██╔╝██║ ██╔══╝   ╚════██║ ██╔══██║     ██║▄▄ ██║    ██║       ██║
  ██║ ╚═╝ ██║ ███████╗ ███████║ ██║  ██║     ╚██████╔╝    ██║       ██║
  ╚═╝     ╚═╝ ╚══════╝ ╚══════╝ ╚═╝  ╚═╝      ╚══▀▀═╝     ╚═╝       ╚═╝
        Client Meshtastic nodeless · Gestion de crise · MQTT · Web
```

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-660066?logo=eclipsemosquitto&logoColor=white)](https://mosquitto.org/)
[![Meshtastic](https://img.shields.io/badge/Meshtastic-mesh-00B894)](https://meshtastic.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Nodeless** = sans radio LoRa sur le PC. MeshQTT simule un nœud Meshtastic via MQTT, comme une gateway, depuis votre navigateur.

---

## En bref

| | |
|---|---|
| **Quoi** | Poste de commandement web pour réseau mesh Meshtastic |
| **Comment** | Pont MQTT protobuf (8 canaux, chiffrement PSK) |
| **Pour qui** | Secours, pompiers, gestion de crise |
| **Où** | [http://127.0.0.1:8080](http://127.0.0.1:8080) en local |

---

## Architecture réseau

```mermaid
flowchart TB
    subgraph MESH["🌐 Mesh LoRa"]
        N1["Nœud A"]
        N2["Nœud B"]
        GW["📻 Radio gateway<br/>Meshtastic"]
        N1 <-->|LoRa| GW
        N2 <-->|LoRa| GW
    end

    subgraph PC["💻 Votre PC"]
        MQ["🖥️ MeshQTT<br/>(navigateur)"]
        BR["🐳 Mosquitto<br/>:1883"]
        MQ <-->|127.0.0.1| BR
    end

    GW <-->|MQTT LAN<br/>192.168.x.x| BR

    style MQ fill:#1a1a2e,color:#eee
    style BR fill:#16213e,color:#eee
    style GW fill:#0f3460,color:#eee
```

### Qui se connecte où ?

```
┌─────────────────────────────────────────────────────────────────┐
│  MÊME BROKER Mosquitto — DEUX CLIENTS DIFFÉRENTS                │
├────────────────────────────┬────────────────────────────────────┤
│  MeshQTT (navigateur)      │  Radio Meshtastic (gateway)        │
├────────────────────────────┼────────────────────────────────────┤
│  Broker : 127.0.0.1        │  Broker : IP LAN du PC             │
│  Port   : 1883             │  Port   : 1883                     │
│  Topic  : msh/EU_868       │  Topic  : identique (Gaulix)       │
│  Auth   : (vide)           │  Auth   : (vide)                   │
└────────────────────────────┴────────────────────────────────────┘
         ⚠️  Ne pas mettre 127.0.0.1 sur la radio — c'est elle-même !
```

Guide détaillé : [docs/mqtt-gateway.md](docs/mqtt-gateway.md)

### Root topic — réseau Gaulix

| Paramètre | Valeur |
|-----------|--------|
| **Root topic** | **`msh/EU_868`** |
| **Bande** | **Même topic** en 433 ou 868 MHz (crossband via le serveur MQTT) |

Laisser la valeur par défaut côté radio si elle propose déjà `msh/EU_868`. **Identique** sur MeshQTT, la gateway et tout client du même mesh.

Exemples de topics :

- Abonnement : `msh/EU_868/Fr_Balise/#`
- Publication : `msh/EU_868/Fr_Balise/!a1b2c3d4`

> Ne pas confondre avec le broker public Meshtastic (`msh/EU_868/2/e/`…) — format différent. Les anciens topics (`msh/EU_868/2/e/`, `msh/EU/433/2/e/`) sont migrés automatiquement vers `msh/EU_868/` à l'enregistrement.

Détail des paramètres : [docs/configuration.md](docs/configuration.md)

---

## Interface (aperçu texte)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  MeshQTT          [Statut]  [Info Routes 42]  [Carte]  [MQTT] [Meshtastic]  │
│                                                      [Connecter] [Déconnecter]│
├──────────────┬───────────────────────────────────────────────┬───────────────┤
│ PRÉDÉFINIS   │  MESSAGES (fil temps réel WebSocket)          │  NŒUDS (42)   │
│              │                                               │               │
│ ▶ Pompier    │  [12:04] Fr_Balise : PARTI                   │  !a1b2c3d4    │
│ ▶ Secours    │  [12:05] D_Ligerien : renfort demandé         │  !e5f6g7h8    │
│ ▶ Crise      │  ...                                          │  ...          │
│              ├───────────────────────────────────────────────┤               │
│ [+ Nouveau]  │  CLAVIER — Groupe / Direct                    │               │
│              │  [Canal ▼] [Message...............] [Envoyer] │               │
│              ├───────────────────────────────────────────────┤               │
│              │  INFO ROUTES 42 (Internet) → remontée mesh    │               │
└──────────────┴───────────────────────────────────────────────┴───────────────┘
```

---

## Flux d'un message

```mermaid
sequenceDiagram
    participant U as Utilisateur
    participant W as MeshQTT Web
    participant F as FastAPI
    participant M as Mosquitto
    participant R as Radio gateway
    participant L as Mesh LoRa

    U->>W: Saisie message + Envoyer
    W->>F: POST /api/send
    F->>M: Publish protobuf
    M->>R: Topic msh/EU_868/Canal/!node
    R->>L: Émission LoRa
    L->>R: Réponse mesh
    R->>M: Publish
    M->>F: on_message
    F->>W: WebSocket /ws
    W->>U: Affichage fil
```

---

## Origines

MeshQTT est une **adaptation web** de [**Connect**](https://github.com/pdxlocations/connect) (*A Nodeless MQTT Client for Meshtastic*) par [**pdxlocations**](https://github.com/pdxlocations).

```
  Connect (Python + Tkinter)          MeshQTT (ce dépôt)
  ─────────────────────────         ─────────────────────
  mqtt-connect.py                 →   app/mqtt_client.py + API REST
  Client desktop                  →   Serveur FastAPI + navigateur
  Carte folium optionnelle        →   Waypoints WAYPOINT_APP + Leaflet
  —                               →   Info Routes 42, prédéfinis, 8 canaux UI
```

| | |
|---|---|
| **Projet d’origine** | [github.com/pdxlocations/connect](https://github.com/pdxlocations/connect) |
| **Concept repris** | Pont MQTT Meshtastic sans nœud radio (protobuf, PSK) |
| **Écosystème** | [Meshtastic](https://meshtastic.org) · [meshtastic-mqtt-client](https://github.com/arankwende/meshtastic-mqtt-client) |

Détails : [docs/origines.md](docs/origines.md)

---

## Fonctionnalités

```
  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
  │   MQTT      │  │  MESSAGES   │  │   CANAUX    │  │ PRÉDÉFINIS  │
  │ multi-canal │  │ temps réel  │  │  0 → 7 PSK  │  │  rubriques  │
  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
  │  CLAVIER    │  │ INFO ROUTE  │  │   CARTE     │  │   THÈME     │
  │ grp/direct  │  │ 42 + mesh   │  │  /map OSM   │  │  jour/nuit  │
  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
```

| Domaine | Description |
|---------|-------------|
| **MQTT** | Broker local ou distant, root topic Gaulix `msh/EU_868`, multi-canaux |
| **Messages** | Fil WebSocket, déchiffrement PSK |
| **Nœuds** | Liste des nœuds visibles sur le mesh |
| **Canaux** | 8 slots, rôles PRINCIPAL / SECONDAIRE / DESACTIVE |
| **Prédéfinis** | Pompier, Secours, Crise… → `data/presets.json` |
| **Info Routes 42** | Bulletin Loire, waypoints, remontée mesh |
| **Carte** | Leaflet sur `/map` |

---

## Démarrage rapide

```mermaid
flowchart LR
    A["1. git clone"] --> B["2. venv + pip"]
    B --> C["3. docker compose up"]
    C --> D["4. uvicorn :8080"]
    D --> E["5. Config MQTT"]
    E --> F["6. Connecter"]
    F --> G["✓ Opérationnel"]
```

### Prérequis

- Python **3.11+** · **Docker** · Navigateur moderne

### Installation

```powershell
git clone https://github.com/F4EED/MeshQTT.git
cd MeshQTT

python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt

docker compose up -d
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8080
```

→ Ouvrir **[http://127.0.0.1:8080](http://127.0.0.1:8080)**

### Checklist premier usage

```
  [ ] Mosquitto actif     →  docker ps --filter name=meshqtt-mosquitto
  [ ] MQTT configuré      →  127.0.0.1:1883 + root topic Gaulix : msh/EU_868
  [ ] Canaux Meshtastic   →  noms + clés PSK alignés avec la radio
  [ ] Connecter           →  bouton en haut à droite
  [ ] Radio gateway       →  module MQTT vers IP LAN du PC
  [ ] Nœuds visibles      →  colonne de droite
```

---

## Configuration

```
  data/settings.json  ──►  config embarquée (canaux, MQTT, UI)
         │
         ▼
  localStorage        ──►  copie navigateur (prioritaire si présente)
         │
         ▼
  /api/settings       ──►  sync serveur ↔ client
```

| Fichier | Rôle | Sur GitHub |
|---------|------|------------|
| `data/settings.json` | MQTT, canaux, identité | ❌ (gitignore — clés PSK) |
| `data/presets.json` | Messages prédéfinis | ✅ |
| `docker/mosquitto/` | Broker local | ✅ |

Documentation : [docs/configuration.md](docs/configuration.md)

---

## Stack technique

```
                    ┌──────────────────┐
                    │    Navigateur    │
                    │  HTML · CSS · JS │
                    └────────┬─────────┘
                             │ HTTP / WS
                    ┌────────▼─────────┐
                    │  FastAPI       │
                    │  uvicorn       │
                    ├────────────────┤
                    │ mqtt_client.py │◄── paho-mqtt · protobuf
                    │ mesh_crypto.py │◄── AES-CTR
                    │ inforoute42.py │◄── proxy HTTP
                    └────────┬─────────┘
                             │ MQTT :1883
                    ┌────────▼─────────┐
                    │ Mosquitto Docker │
                    └──────────────────┘
```

| Composant | Technologie |
|-----------|-------------|
| Backend | FastAPI, uvicorn |
| MQTT | paho-mqtt, protobuf Meshtastic |
| Crypto | AES-CTR |
| Frontend | HTML, CSS, JavaScript vanilla |
| Carte | Leaflet + OpenStreetMap |

---

## Documentation

| Document | Contenu |
|----------|---------|
| [docs/installation.md](docs/installation.md) | Installation détaillée |
| [docs/mqtt-gateway.md](docs/mqtt-gateway.md) | Brancher une radio Meshtastic |
| [docs/configuration.md](docs/configuration.md) | MQTT, canaux, settings |
| [docs/utilisation.md](docs/utilisation.md) | Interface web |
| [docs/inforoute42.md](docs/inforoute42.md) | Info Routes 42 |
| [docs/cartographie.md](docs/cartographie.md) | Carte Leaflet |
| [docs/depannage.md](docs/depannage.md) | Dépannage |
| [docs/architecture.md](docs/architecture.md) | API, protocole |
| [docs/origines.md](docs/origines.md) | Connect → MeshQTT |

---

## Crédits

- [**Connect**](https://github.com/pdxlocations/connect) — [pdxlocations](https://github.com/pdxlocations)
- [**Meshtastic**](https://meshtastic.org) — protocole et écosystème mesh

---

## Licence

MIT License — voir [LICENSE](LICENSE).  
Vérifiez aussi la licence de [Connect](https://github.com/pdxlocations/connect) pour le code d’origine.
