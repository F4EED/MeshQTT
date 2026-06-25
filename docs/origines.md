# Origines du projet

## Projet de départ

**MeshQTT** est une adaptation web du client Meshtastic **nodeless** (sans radio) :

| | |
|---|---|
| **Projet d’origine** | [**Connect**](https://github.com/pdxlocations/connect) — *A Nodeless MQTT Client for Meshtastic* |
| **Auteur** | [**pdxlocations**](https://github.com/pdxlocations) |
| **Dépôt GitHub** | [https://github.com/pdxlocations/connect](https://github.com/pdxlocations/connect) |

Nous sommes partis de ce projet pour construire une interface **navigateur** (FastAPI + HTML/JS) orientée **gestion de crise** (département de la Loire), avec des évolutions propres :

- Interface web au lieu de Tkinter (`mqtt-connect.py`)
- Messages prédéfinis, clavier groupe/direct, Info Routes 42
- Envoi de waypoints Meshtastic depuis les signalements routiers
- Broker MQTT sur Raspberry Pi (Mosquitto LAN)

Le cœur du concept — **pont MQTT protobuf Meshtastic sans nœud radio** — reprend l’approche de Connect.

## Remerciements (chaîne d’inspiration)

Le README de Connect cite également :

- [arankwende/meshtastic-mqtt-client](https://github.com/arankwende/meshtastic-mqtt-client)
- [joshpirihi/meshtastic-mqtt](https://github.com/joshpirihi/meshtastic-mqtt)

Et l’écosystème [Meshtastic](https://meshtastic.org).

## Différences principales Connect → MeshQTT

| Connect (origine) | MeshQTT (ce dépôt) |
|-------------------|---------------------|
| Client Python + Tkinter | Serveur FastAPI + navigateur |
| `mqtt-connect.py` | `app/mqtt_client.py` + API REST |
| Carte folium optionnelle | Waypoints via protocole `WAYPOINT_APP` |
| — | Info Routes 42, prédéfinis, 8 canaux UI |

## Crédit

Merci à **pdxlocations** pour [Connect](https://github.com/pdxlocations/connect) et la base du client MQTT nodeless Meshtastic.

Si vous améliorez MeshQTT, pensez à remonter les corrections génériques au projet d’origine lorsque c’est pertinent.
