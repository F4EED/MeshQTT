# Installation

## Prérequis

- **Windows 10/11** (ou Linux/macOS avec adaptations des commandes)
- **Python 3.11+** (testé avec 3.14)
- **Raspberry Pi** avec Mosquitto sur le LAN (voir [pi-mosquitto.md](pi-mosquitto.md), ex. `192.168.1.66:1883`)
- Navigateur moderne (Chrome, Firefox, Edge)

## Cloner ou copier le projet

```powershell
cd C:\MeshQTT
```

## Environnement Python

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

Dépendances principales : FastAPI, uvicorn, paho-mqtt, meshtastic (protobuf), cryptography.

## Broker MQTT (Raspberry Pi)

Le broker **Mosquitto** tourne sur le **Pi**, pas sur le PC MeshQTT.

| Paramètre | Valeur type |
|-----------|-------------|
| Hôte | `192.168.1.66` (IP LAN du Pi) |
| Port | **1883** |
| Root topic | **`msh/EU_868`** |

Installation ou audit du Pi :

```powershell
cd C:\MeshQTT
.\.venv\Scripts\python.exe scripts\pi_mosquitto_remote_setup.py
```

Vérifier depuis le PC :

```powershell
curl http://127.0.0.1:8080/api/mqtt/health
```

(`reachable: true` si le Pi répond sur le port 1883 — broker configuré dans `data/settings.json`.)

## Lancer MeshQTT

```powershell
cd C:\MeshQTT
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Interface : [http://127.0.0.1:8080](http://127.0.0.1:8080)

### Lancement en arrière-plan

Laisser la fenêtre PowerShell ouverte, ou utiliser un gestionnaire de processus / tâche planifiée.

## Premier accès

1. Ouvrir l’URL ci-dessus
2. Aller dans **MQTT** → broker `192.168.1.66`, port `1883`, root topic **`msh/EU_868`** (réseau Gaulix)
3. Aller dans **Meshtastic** → canaux, nom court, ID nœud
4. Cliquer **Connecter**

Pour brancher une **radio Meshtastic** (gateway MQTT) sur le broker du Pi : [mqtt-gateway.md](mqtt-gateway.md).

Pour le **downlink mesh** (messages vers les nœuds LoRa) : canal radio **`mqtt`** (slot 6) + downlink ON sur chaque canal utilisé — voir [mqtt-gateway.md#downlink-mesh--json-sendtext-recommandé-broker-privé](mqtt-gateway.md#downlink-mesh--json-sendtext-recommandé-broker-privé).

Voir [configuration.md](configuration.md) pour le détail des paramètres.

## Mise à jour du code

Après un `git pull` ou modification du backend :

```powershell
.\.venv\Scripts\pip install -r requirements.txt
# Redémarrer uvicorn (Ctrl+C puis relancer)
```

Le frontend (`app/static/`) se recharge avec **Ctrl+F5** dans le navigateur.
