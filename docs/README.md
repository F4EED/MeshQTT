# Documentation MeshQTT

Index de la documentation du projet. **Ces fichiers doivent rester synchronisés avec le code** lors de chaque évolution notable.

| Fichier | Public | Description |
|---------|--------|-------------|
| [origines.md](origines.md) | Tous | Projet de départ [pdxlocations/connect](https://github.com/pdxlocations/connect) |
| [installation.md](installation.md) | Tous | Installation et premier démarrage |
| [configuration.md](configuration.md) | Opérateur | Paramètres MQTT, Meshtastic, persistance |
| [mqtt-gateway.md](mqtt-gateway.md) | Opérateur | Gateway MQTT, downlink broadcast + DM PKI |
| [pi-mosquitto.md](pi-mosquitto.md) | Opérateur | Broker Mosquitto sur Raspberry Pi (LAN) |
| [utilisation.md](utilisation.md) | Opérateur | Manipulation de l’interface web |
| [inforoute42.md](inforoute42.md) | Opérateur | Zone Info Routes 42 (Internet) |
| [cartographie.md](cartographie.md) | Opérateur | Carte Leaflet des signalements |
| [depannage.md](depannage.md) | Tous | Dépannage et maintenance |
| [architecture.md](architecture.md) | Développeur | Code, API REST, protocole mesh |

## Mise à jour

Lors d’un changement de fonctionnalité, mettre à jour :

1. Le doc concerné (section précise)
2. Le [README.md](../README.md) si le démarrage rapide ou la liste des fonctionnalités change
3. Cet index si un nouveau fichier est ajouté
