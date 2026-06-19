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
| **Adresse (Address)** | IP **LAN** du PC qui héberge Mosquitto (ex. `192.168.1.74`) |
| **Port** | `1883` |
| **Utilisateur / mot de passe** | Laisser **vide** |
| **Root topic** | Identique à MeshQTT (ex. `msh/EU_868/2/e/`) |
| **Chiffrement MQTT** | **Activé** (recommandé ; MeshQTT déchiffre avec les clés de canal) |

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
| Broker | `127.0.0.1` (correct depuis le PC) |
| Port | `1883` |
| Username / Password | vides |
| Root topic | `msh/EU_868/2/e/` (ou celui de votre région / bande) |

Exemple actuel (`data/settings.json`) :

```json
{
  "mqtt": {
    "broker": "127.0.0.1",
    "port": 1883,
    "username": "",
    "password": "",
    "root_topic": "msh/EU_868/2/e/"
  }
}
```

## Root topic — choisir la bonne valeur

Le root topic doit correspondre à votre **région LoRa** et **bande** :

| Exemple | Usage |
|---------|--------|
| `msh/EU_868/2/e/` | Europe, bande 868 MHz |
| `msh/EU/433/2/e/` | Europe, bande 433 MHz |

**Identique** sur la radio, dans MeshQTT et sur toute autre gateway du même mesh.

Topics Meshtastic :

- Abonnement gateway : `{root_topic}{nom_canal}/#`
- Publication : `{root_topic}{nom_canal}/{node_id}`

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
| MeshQTT connecté mais pas de nœuds | Pas de gateway MQTT active sur le mesh |
| Messages illisibles / erreur déchiffrement | Clé PSK différente entre radio et MeshQTT |
| Envoi OK, rien sur le mesh | Nom de canal différent, ou pas de gateway relais |

Voir [depannage.md](depannage.md) pour le détail.

## Voir aussi

- [configuration.md](configuration.md) — paramètres MeshQTT
- [installation.md](installation.md) — Docker et premier démarrage
- [architecture.md](architecture.md) — protocole MQTT / protobuf
