# Dépannage

## Le serveur ne démarre pas

**Port 8080 déjà utilisé**

```powershell
netstat -ano | findstr ":8080"
Stop-Process -Id <PID> -Force
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8080
```

## `/api/inforoute42` → 404

Le serveur tourne avec une **ancienne version** du code. **Redémarrer uvicorn** après toute modification Python.

## Pas de coordonnées sous les signalements

Même cause : backend sans champs `point_xy` / `point_latlng`. Redémarrer uvicorn, puis **Ctrl+F5** dans le navigateur.

## Connexion MQTT échoue

1. **Un seul Mosquitto** doit écouter sur le port **1883** (éviter plusieurs conteneurs Docker en parallèle).
2. Broker MeshQTT recommandé :

   ```powershell
   cd C:\MeshQTT
   docker compose up -d
   docker ps --filter name=meshqtt-mosquitto
   netstat -ano | findstr ":1883"
   ```

3. Diagnostic API : [http://127.0.0.1:8080/api/mqtt/health](http://127.0.0.1:8080/api/mqtt/health) → `"reachable": true`
4. Broker = `127.0.0.1:1883` dans MeshQTT
5. Root topic cohérent avec vos gateways
6. Au moins **un canal activé** avec un nom

### Plusieurs Mosquitto Docker (conflit fréquent)

Si vous aviez plusieurs conteneurs (`mosquitto-local`, `MosquittoTest`, etc.), ne garder **qu'un seul** exposant `1883` :

```powershell
docker ps --format "table {{.Names}}\t{{.Ports}}"
docker stop mosquitto-local Mosquitto_simple MosquittoTest   # exemples
cd C:\MeshQTT
docker compose up -d
```

Le conteneur attendu pour MeshQTT : **`meshqtt-mosquitto`** (`0.0.0.0:1883->1883/tcp`).
Un conteneur Mosquitto **sans** mapping de port (`Ports` vide) n'est pas joignable depuis MeshQTT sur le PC.

## Déchiffrement échoué

La clé PSK du canal dans MeshQTT doit correspondre à celle du mesh. Canal sans clé (`key` vide ou `AQ==`) = non chiffré.

## Envoi message OK mais rien sur le mesh

- Vérifier qu’une **gateway MQTT** (nœud avec connexion mesh + MQTT) est connectée au même broker
- Vérifier le **nom du canal** (identique côté radio)
- Logs uvicorn / broker Mosquitto

## Erreur `HW_MODEL` / protobuf

Utiliser `mesh_pb2.HardwareModel.PRIVATE_HW` (pas `HW_MODEL_PRIVATE_HW`). Code corrigé dans `app/mqtt_client.py`.

## Waypoint invisible sur la carte

- Client Meshtastic à jour
- Même canal / clé que l’émetteur
- Expiration non dépassée
- Broadcast requis (destination par défaut)

## Frontend ne se met pas à jour

Rechargement forcé : **Ctrl+F5** (cache `app.js` / `style.css`).

## Info Routes inaccessible

- Connexion Internet sur la machine serveur
- Site [inforoute42.fr](https://www.inforoute42.fr/) joignable
- Erreur affichée dans le statut de la zone ; pas de toast en actualisation auto

## Redémarrage complet type

```powershell
docker compose restart
Stop-Process -Id <pid_uvicorn> -Force
cd C:\MeshQTT
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8080
```

## Logs utiles

- Terminal uvicorn : requêtes HTTP, erreurs Python
- Console navigateur (F12) : WebSocket, fetch API
