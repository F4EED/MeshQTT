# Connexion d’un nœud Meshtastic (gateway MQTT)

Guide pour relier une **radio Meshtastic** (gateway mesh ↔ MQTT) au broker Mosquitto local de MeshQTT.

## Architecture

```
Radio Meshtastic  ←→  mesh LoRa  ←→  autres nœuds
       ↕ MQTT (LAN)
   Mosquitto (PC, port 1883)
       ↕ MQTT
   MeshQTT (navigateur, nœud virtuel sans radio)
```

MeshQTT ne parle pas en LoRa : il simule un nœud via MQTT. Une **gateway** (nœud avec module MQTT activé) fait le pont entre le mesh radio et le broker.

> **Broker sur Raspberry Pi** : voir [pi-mosquitto.md](pi-mosquitto.md) (ex. `192.168.1.66`). La radio pointe vers l’IP du Pi ; MeshQTT sur le PC utilise la **même** adresse, pas `127.0.0.1`.

## Broker Mosquitto sur cette machine

| Paramètre | Valeur |
|-----------|--------|
| Image Docker | `eclipse-mosquitto:2` |
| Port | **1883** (sans TLS en local) |
| Authentification | **Aucune** (`allow_anonymous true`) |
| Config | `docker/mosquitto/mosquitto.conf` |

Démarrage :

```powershell
docker compose up -d
docker ps
```

## Config sur le nœud Meshtastic (Module MQTT)

Dans l’application Meshtastic ou via CLI : **Module config → MQTT**.

| Paramètre | Valeur |
|-----------|--------|
| **MQTT activé** | Oui |
| **Adresse (Address)** | IP **LAN** du broker (ex. `192.168.1.66` sur le Pi) — **sans** `:1883` dans ce champ |
| **Port** | `1883` |
| **Utilisateur / mot de passe** | Laisser **vide** |
| **Root topic** | Identique à MeshQTT : **`msh/EU_868`** (réseau Gaulix, crossband) |
| **TLS / chiffrement MQTT** (connexion au broker) | **Désactivé** pour Mosquitto local sans certificat (Pi ou Docker). Si activé avec le port 1883, le test Android expire souvent après **5000 ms**. |

> **Important** : ne pas mettre `127.0.0.1` sur la radio — « localhost » désigne la radio elle-même, pas votre PC.

### Trouver l’IP du PC (Windows)

```powershell
Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -notlike '127.*' -and $_.InterfaceAlias -notlike '*WSL*' } |
  Select-Object IPAddress, InterfaceAlias
```

Utiliser l’adresse du réseau local (souvent Wi‑Fi ou Ethernet, ex. `192.168.1.x`).

## Config dans MeshQTT (interface web)

Menu **MQTT** (ou `data/settings.json`) :

| Paramètre | Valeur |
|-----------|--------|
| Broker | `192.168.1.66` |
| Port | `1883` |
| Username / Password | vides |
| Root topic | `msh/EU_868` |

Exemple actuel (`data/settings.json`) :

```json
{
  "mqtt": {
    "broker": "192.168.1.66",
    "port": 1883,
    "username": "",
    "password": "",
    "root_topic": "msh/EU_868"
  }
}
```

## Root topic — réseau Gaulix

Le réseau **Gaulix** préconise :

| Paramètre | Valeur |
|-----------|--------|
| Root topic | **`msh/EU_868`** |
| Bande | **Même topic** que le nœud soit en 433 ou 868 MHz (crossband via MQTT) |

Laisser la valeur par défaut côté radio si elle propose déjà `msh/EU_868`.

Le firmware Meshtastic **ajoute** `/2/json/` ou `/2/e/` après ce root (segment fixe, pas une erreur de config).

| Réglage gateway | Topic uplink (ex.) |
|-----------------|-------------------|
| JSON enabled + uplink | `msh/EU_868/2/json/D_Ligerien/!node` |
| JSON off + uplink | `msh/EU_868/2/e/D_Ligerien/!node` ou `msh/EU_868//2/e/…` si root avec `/` final |

MeshQTT écoute ces topics et décode le **JSON** ou le **protobuf**.

| Réglage radio | Recommandation |
|---------------|----------------|
| Root topic | `msh/EU_868` |
| Uplink enabled | Oui (par canal utilisé) |
| JSON enabled | Oui ou non — MeshQTT gère les deux |

## Canaux et clés — alignement obligatoire

Les canaux configurés dans MeshQTT (**Réglages Meshtastic**) doivent correspondre à la radio :

| Champ MeshQTT | Côté radio |
|---------------|------------|
| `name` | Nom exact du canal (ex. `Fr_Balise`, `D_Ligerien`) |
| `key` | Clé PSK base64 identique |
| `enabled` | Canal utilisé pour send/receive |

- Canal **sans clé** ou `AQ==` : trafic non chiffré sur MQTT.
- Canal **chiffré** : la clé PSK doit être **strictement la même** des deux côtés, sinon « Déchiffrement échoué » (voir [depannage.md](depannage.md)).

## Réseau et firewall

1. La radio (Wi‑Fi ou Ethernet) et le PC doivent être sur le **même LAN**.
2. **Firewall Windows** : autoriser les connexions entrantes sur le port **1883** si la gateway ne se connecte pas.
3. Vérifier que Mosquitto écoute : `netstat -ano | findstr ":1883"`.

## Vérification

1. `docker ps` — conteneur Mosquitto actif.
2. Configurer MQTT sur le nœud Meshtastic → sauvegarder (redémarrer la radio si besoin).
3. MeshQTT → **Connecter**.
4. Les nœuds du mesh apparaissent dans la colonne de droite ; les messages circulent dans les deux sens.

## Dépannage rapide

| Symptôme | Piste |
|----------|--------|
| Radio ne se connecte pas au broker | Mauvaise IP (127.0.0.1), firewall, Mosquitto arrêté |
| Test Android « Délai expiré 5000 ms » | **TLS activé** alors que le broker est en 1883 sans certificat ; ou téléphone pas sur le même WiFi que le Pi ; adresse avec `:1883` dans le champ Adresse |
| MeshQTT connecté mais pas de nœuds | Pas de gateway MQTT active sur le mesh |
| Messages illisibles / erreur déchiffrement | Clé PSK différente entre radio et MeshQTT |
| Envoi OK, rien sur le mesh | **Downlink enabled** sur le canal côté gateway ; nom de canal identique ; PSK identique ; paquet MQTT chiffré (MeshQTT) — voir ci-dessous |

Voir [depannage.md](depannage.md) pour le détail.

## Voir aussi

- [configuration.md](configuration.md) — paramètres MeshQTT
- [installation.md](installation.md) — Docker et premier démarrage
- [architecture.md](architecture.md) — protocole MQTT / protobuf
