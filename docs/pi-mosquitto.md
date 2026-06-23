# Mosquitto sur Raspberry Pi (192.168.1.66)

Broker MQTT dédié au mesh Meshtastic, accessible depuis le LAN WiFi.

## État constaté (audit SSH)

| Élément | Résultat |
|---------|----------|
| Hôte | `mosquitto` — IP **192.168.1.66** (wlan0) |
| Paquet `mosquitto` | **Non installé** |
| Port **1883** | Fermé (service absent) |
| Utilisateur SSH | `mosquitto` (sudo sans mot de passe) |

Le nœud Meshtastic ne peut pas publier tant que Mosquitto n’écoute pas sur `192.168.1.66:1883`.

## Installation automatique (depuis le PC MeshQTT)

```powershell
cd C:\MeshQTT
.\.venv\Scripts\python.exe scripts\pi_mosquitto_remote_setup.py
```

Le script installe Mosquitto, applique une config Meshtastic-friendly et démarre la **capture** des messages.

## Configuration Meshtastic (radio gateway)

Dans l’app Meshtastic ou `meshtastic --set` :

| Paramètre | Valeur |
|-----------|--------|
| `mqtt.enabled` | `true` |
| `mqtt.address` | `192.168.1.66` |
| `mqtt.username` / `mqtt.password` | vides (broker LAN sans auth) |
| TLS / chiffrement MQTT (vers le broker) | **désactivé** (port 1883 non chiffré) |
| `mqtt.root` | `msh/EU_868` |
| Par canal (0–7) | **Uplink enabled** (et downlink si besoin) |

Topics publiés par la radio : `msh/EU_868/2/e/{canal}/!node` ou `…/2/json/…` si JSON activé.

## MeshQTT (PC)

Dans **Paramètres → MQTT** :

| Champ | Valeur |
|-------|--------|
| Broker | `192.168.1.66` |
| Port | `1883` |
| Root topic | `msh/EU_868` |

Puis **Connecter** (ou redémarrer uvicorn — connexion auto si canaux actifs).

## Conserver les messages MQTT

Deux mécanismes après setup :

1. **Capture horodatée** (service `meshtastic-mqtt-capture`)  
   - Fichiers : `/var/lib/meshtastic-mqtt-capture/meshtastic-YYYYMMDD.log`  
   - Format : `timestamp<TAB>topic payload` (mode `-v` de `mosquitto_sub`)  
   - Rotation : **14 jours** (`logrotate`)

2. **Journal Mosquitto** : `/var/log/mosquitto/mosquitto.log` (connexions, erreurs)

### Commandes utiles sur le Pi

```bash
# État
systemctl status mosquitto meshtastic-mqtt-capture

# Dernières lignes capturées
tail -f /var/lib/meshtastic-mqtt-capture/meshtastic-$(date +%Y%m%d).log

# Écoute live
mosquitto_sub -h 127.0.0.1 -t 'msh/#' -v

# Espace disque capture
du -sh /var/lib/meshtastic-mqtt-capture/
```

### Installation manuelle (sans script PC)

Voir le contenu de `scripts/pi_mosquitto_setup.sh` (listener `0.0.0.0:1883`, `allow_anonymous true`, service capture).

## Sécurité (optionnel)

Sur un LAN de confiance, `allow_anonymous true` suffit pour tester. En production :

- Créer un utilisateur MQTT : `sudo mosquitto_passwd -c /etc/mosquitto/passwd mesh`
- Remplacer `allow_anonymous true` par `password_file /etc/mosquitto/passwd`
- Reporter les mêmes identifiants dans la radio Meshtastic et MeshQTT

## Dépannage

| Symptôme | Action |
|----------|--------|
| Radio ne se connecte pas | Ping `192.168.1.66` depuis le téléphone ; port 1883 ouvert : `ss -tlnp \| grep 1883` sur le Pi |
| MeshQTT `rx_count` = 0 | Broker MeshQTT = `192.168.1.66`, pas `127.0.0.1` |
| Fichier capture vide | Vérifier `systemctl status meshtastic-mqtt-capture` ; traffic sur `mosquitto_sub -t 'msh/#' -v` |
