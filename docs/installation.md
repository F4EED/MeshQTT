# Installation

## Prérequis

- **Windows 10/11** (ou Linux/macOS avec adaptations des commandes)
- **Python 3.11+** (testé avec 3.14)
- **Docker Desktop** (pour Mosquitto local, recommandé)
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

## Broker MQTT local (Docker)

**Un seul** broker Mosquitto doit tourner sur le port **1883** :

```powershell
docker compose up -d
```

- Conteneur : **`meshqtt-mosquitto`**
- Image : `eclipse-mosquitto:2`
- Port : **1883** (`0.0.0.0:1883->1883/tcp`)
- Config : `docker/mosquitto/mosquitto.conf`

Si d'autres conteneurs Mosquitto existent déjà sur la machine, les arrêter avant (voir [depannage.md](depannage.md)).

Vérifier :

```powershell
docker ps --filter name=meshqtt-mosquitto
netstat -ano | findstr ":1883"
curl http://127.0.0.1:8080/api/mqtt/health
```

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
2. Aller dans **MQTT** → broker `127.0.0.1`, port `1883`, root topic **`msh/EU_868`** (réseau Gaulix)
3. Aller dans **Meshtastic** → canaux, nom court, ID nœud
4. Cliquer **Connecter**

Pour brancher une **radio Meshtastic** (gateway MQTT) sur le broker local : [mqtt-gateway.md](mqtt-gateway.md).

Voir [configuration.md](configuration.md) pour le détail des paramètres.

## Mise à jour du code

Après un `git pull` ou modification du backend :

```powershell
.\.venv\Scripts\pip install -r requirements.txt
# Redémarrer uvicorn (Ctrl+C puis relancer)
```

Le frontend (`app/static/`) se recharge avec **Ctrl+F5** dans le navigateur.
