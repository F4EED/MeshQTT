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

## Messages visibles sur Mosquitto mais pas dans MeshQTT

1. **MeshQTT connecté ?** La barre de statut doit afficher « Connecté » (connexion auto au démarrage si des canaux sont actifs). Sinon : bouton **Connecter**.

2. **Même broker ?** Sur Windows, `localhost` peut pointer vers `::1` (WSL / autre Mosquitto) alors que MeshQTT utilise `127.0.0.1` (Docker `meshqtt-mosquitto`). Configurez le **même** hôte partout : `127.0.0.1` ou l’IP LAN du PC (`192.168.x.x`). Diagnostic : [http://127.0.0.1:8080/api/mqtt/health](http://127.0.0.1:8080/api/mqtt/health)

3. Vérifier le **topic** avec `mosquitto_sub` **sur le broker MeshQTT** :

   ```powershell
   docker exec -it meshqtt-mosquitto mosquitto_sub -h localhost -t "msh/EU_868/#" -v
   ```

4. Topic attendu avec firmware Meshtastic : `msh/EU_868/2/json/{canal}/!node` ou `…/2/e/…` — le **`/2/`** est normal (ajouté par la radio).

5. **Nom de canal** identique dans MeshQTT et sur la radio (`D_Ligerien`, etc.).

6. **Uplink enabled** sur le canal côté gateway.

7. Redémarrer uvicorn après mise à jour du backend. La reconnexion MQTT est automatique au démarrage du serveur.

8. **Diagnostic MeshQTT** : [http://127.0.0.1:8080/api/status](http://127.0.0.1:8080/api/status) affiche `rx_count` et `last_topic`. Si `rx_count` reste à **0** alors que MQTT Explorer voit des messages, ce n’est **pas le même broker** (souvent `localhost` ≠ `127.0.0.1` sous Windows). Dans MQTT Explorer, connectez-vous à la **même IP** que dans les paramètres MeshQTT.

## Souci de `//` à la place de `/` dans les topics

Symptôme typique : la radio publie sur `msh/EU_868//2/e/Fr_Balise/!node` (deux slashes après le root) alors qu’un client envoie sur `msh/EU_868/2/e/Fr_Balise/!node` (un seul slash). En MQTT ce ne sont **pas** les mêmes topics — uplink et downlink peuvent rater.

**Cause** : le firmware Meshtastic concatène `root_topic` + `/2/e/`. Si le root se termine déjà par `/` (ex. `msh/EU_868/`), on obtient un **double slash** : `msh/EU_868//2/e/…`.

**Correctifs** :

1. **MeshQTT** (depuis la correction topics) publie et s’abonne comme le firmware (`root + "/2/e/"`), donc avec `//` si le root a un slash final.
2. **Sur la radio**, préférer root topic **`msh/EU_868`** **sans** slash final → topics propres : `msh/EU_868/2/e/…`
3. Vérifier dans MQTT Explorer ou les logs Pi : comparer exactement les chaînes de topic (compter les `/`).

Exemple gateway Pi : `/var/lib/meshtastic-mqtt-capture/meshtastic-YYYYMMDD.log`

## Message visible dans MQTT Explorer mais pas sur le mesh (downlink)

MeshQTT publie bien sur le broker (topic `msh/EU_868//2/e/{canal}/!votre_noeud`) — la gateway doit **relayer** vers le LoRa.

1. **Downlink enabled** sur le **même canal** que l’envoi (app Meshtastic → Canaux → ex. Fr_BlaBla → Downlink → Envoyer).

2. **Nom de canal** strictement identique (`Fr_BlaBla`, pas une variante).

3. **Clé PSK** identique dans MeshQTT et sur la radio pour ce canal.

4. **Chiffrement MQTT** sur la gateway (Module MQTT → *Encryption enabled*) :
   - **Désactivé** (courant sur broker local Pi) → paquets **decoded** en downlink ; MeshQTT envoie `decoded` pour les canaux `AQ==`
   - **Activé** → paquets **chiffrés** obligatoires ; MeshQTT s’aligne sur l’uplink reçu ou chiffre si PSK explicite

5. **Gateway en ligne** : WiFi OK, MQTT connecté au **même** broker (`192.168.1.66`). **Proxy client MQTT désactivé** si la radio a le WiFi (gateway directe).

6. Topic downlink : `msh/EU_868/2/e/{canal}/!votre_noeud` **et** variante `msh/EU_868//2/e/…` (MeshQTT publie les deux ; s’abonne aux deux pour la réception).

7. **Downlink enabled** sur **D_Ligerien** (canal visé), puis **Envoyer** et redémarrer la radio si l’abonnement MQTT ne se met pas à jour.

8. Journal MeshQTT à l’envoi : `↑ MQTT … (decoded)` ou `(chiffré)` — doit correspondre au réglage *Encryption enabled* de la gateway.

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
