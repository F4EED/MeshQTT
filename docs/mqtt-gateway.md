# Connexion d’un nœud Meshtastic (gateway MQTT)

Guide pour relier une **radio Meshtastic** (gateway mesh ↔ MQTT) au broker Mosquitto sur le **Raspberry Pi**.

## Architecture

```
Radio Meshtastic  ←→  mesh LoRa  ←→  autres nœuds
       ↕ MQTT (LAN)
   Mosquitto (Pi, ex. 192.168.1.66:1883)
       ↕ MQTT
   MeshQTT (PC, navigateur — nœud virtuel sans radio)
```

MeshQTT ne parle pas en LoRa : il simule un nœud via MQTT. Une **gateway** (nœud avec module MQTT activé) fait le pont entre le mesh radio et le broker.

> Voir [pi-mosquitto.md](pi-mosquitto.md) pour l’installation du broker sur le Pi. La radio et MeshQTT utilisent la **même IP** (`192.168.1.66`), pas `127.0.0.1`.

## Broker Mosquitto (Raspberry Pi)

| Paramètre | Valeur |
|-----------|--------|
| Hôte | IP LAN du Pi (ex. **`192.168.1.66`**) |
| Port | **1883** (sans TLS) |
| Authentification | **Aucune** (`allow_anonymous true`) |
| Installation | `scripts\pi_mosquitto_remote_setup.py` — voir [pi-mosquitto.md](pi-mosquitto.md) |

Vérifier depuis le PC :

```powershell
curl http://127.0.0.1:8080/api/mqtt/health
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
| **TLS / chiffrement MQTT** (connexion au broker) | **Désactivé** (port 1883 sans certificat sur le Pi). Si activé avec le port 1883, le test Android expire souvent après **5000 ms**. |

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
| Gateway ID | `!ba69d0fc` (optionnel, mémorisé auto) |

Exemple actuel (`data/settings.json`) — voir aussi [configuration.md](configuration.md).

```json
{
  "mqtt": {
    "broker": "192.168.1.66",
    "port": 1883,
    "username": "",
    "password": "",
    "root_topic": "msh/EU_868",
    "gateway_id": "!ba69d0fc"
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

### Gateway MQTT ≠ émetteur mesh

Sur le broker, un message `[D_Ligerien] !d75da807: …` peut être **relayé** par une autre radio WiFi (`!a1d7795c` dans l’enveloppe `gateway_id`). Le **downlink** doit être activé sur **cette** gateway (`!a1d7795c`), pas sur le nœud émetteur.

Diagnostic : `GET http://127.0.0.1:8080/api/mqtt/downlink-debug` après réception d’un message sur le canal.

### Downlink mesh : JSON sendtext (recommandé broker privé)

> **JSON enabled (module MQTT) ≠ canal radio `mqtt`**
>
> | Réglage | Où | Rôle |
> |---------|-----|------|
> | **JSON enabled** | Module MQTT → paramètres | Messages **montants** en JSON sur `…/2/json/{canal}/!node` |
> | **Canal `mqtt`** | Canaux radio (comme Fr_Balise, D_Ligerien…) | **Obligatoire** pour recevoir les commandes **descendantes** sur `…/2/json/mqtt` |
>
> Sans un canal radio nommé exactement **`mqtt`** avec **Downlink ON**, le firmware **ignore** le JSON sendtext — même si JSON enabled est ON dans le module MQTT.

Le downlink **protobuf** (`2/e/{canal}/…`) est visible dans MQTT Explorer mais **souvent ignoré** par le firmware sur broker local. Meshtastic documente un second mécanisme :

Sur la **gateway WiFi** (`!ba69d0fc`) :

1. **Module MQTT** → **JSON enabled** = ON (Encryption OFF, Proxy OFF)
2. **Canaux radio** → canal **6** nommé exactement **`mqtt`** (PSK `AQ==`, uplink + downlink ON côté radio)
3. **Chaque canal cible** (Fr_Balise, Fr_EMCOM, Fr_BlaBla, D_Ligerien, interco, AASC, logistique…) → **Downlink ON** sur la gateway
4. **Index 0–7** identiques entre MeshQTT (`data/settings.json`) et la gateway pour chaque nom de canal
5. **Redémarrer** la radio

MeshQTT envoie alors en parallèle (pour **tout** canal actif, sauf le canal `mqtt` lui-même) :

- `msh/EU_868/2/json/mqtt` — JSON `{"from": <id décimal gateway>, "type": "sendtext", "payload": "…", "channel": <index>}` (index = slot du canal mesh cible, ex. 3 pour D_Ligerien, 0 pour Fr_Balise)
- protobuf `msh/EU_868/2/e/{canal}/!gateway` (suffixe = **gateway**, pas le nœud virtuel MeshQTT)

Le champ **`gateway_id`** dans `data/settings.json` (ex. `!ba69d0fc`) permet le downlink **même sans uplink récent** ; il est mémorisé et propagé à **tous les canaux** au premier message gateway reçu.

### Messages directs (DM)

Depuis Meshtastic **2.5+**, les messages privés utilisent le chiffrement **PKI** (pas le canal Fr_Balise en protobuf).

| | Broadcast | Direct (DM) |
|---|-----------|-------------|
| UI MeshQTT | Clavier **Groupe** | Clavier **Direct** (canal 0) |
| Downlink MQTT | JSON sendtext + protobuf | **JSON sendtext seul** |
| Topic commande | `…/2/json/mqtt` | `…/2/json/mqtt` |
| Corps JSON | `"channel": <index>` | `"to": <node_id>`, `"hopLimit": 7` |
| Uplink confirmation | `…/2/json/{canal}/!gateway` | `…/2/json/PKI/!gateway` |

Prérequis DM :

1. Canal **`mqtt`** + JSON enabled (comme le broadcast)
2. Gateway et destinataire se **connaissent** (nodeinfo / PKI)
3. Destinataire **à portée LoRa** de la gateway

Test :

```powershell
cd C:\MeshQTT
.\.venv\Scripts\python scripts\mqtt_sendtext_test.py --to 2898726677 --text "Test DM"
```

Voir [depannage.md](depannage.md#message-direct-dm--rien-sur-le-wismesh-tag) si le Tag ne reçoit pas le DM.

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

1. La radio (Wi‑Fi ou Ethernet) et le PC MeshQTT doivent être sur le **même LAN** que le Pi.
2. **Firewall** : le Pi doit accepter les connexions MQTT sur **1883** depuis le LAN.
3. Vérifier que Mosquitto écoute sur le Pi : `sudo ss -tlnp | grep 1883` (SSH).

## Vérification

1. Mosquitto actif sur le Pi — voir [pi-mosquitto.md](pi-mosquitto.md).
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
| Envoi OK, rien sur le mesh | **Downlink enabled** sur le canal côté **gateway MQTT** ; canal radio **`mqtt`** + JSON enabled ; `gateway_id` correct — voir [depannage.md](depannage.md) |
| Broadcast OK, DM échoue | PKI : nodeinfo échangé entre gateway et Tag ; tester `mqtt_sendtext_test.py --to <id>` |

Voir [depannage.md](depannage.md) pour le détail.

## Voir aussi

- [configuration.md](configuration.md) — paramètres MeshQTT
- [installation.md](installation.md) — installation et premier démarrage
- [architecture.md](architecture.md) — protocole MQTT / protobuf
