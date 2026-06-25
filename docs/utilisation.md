# Utilisation de l’interface

## En-tête

| Élément | Action |
|---------|--------|
| **Statut** | Connecté / déconnecté, nom du nœud |
| **☾** | Basculer thème jour / nuit |
| **MQTT** | Modale broker, port, root topic |
| **Meshtastic** | Canaux 0–7, identité nœud |
| **Connecter / Déconnecter** | Session MQTT |

## Colonne gauche — Messages prédéfinis

- Rubriques dynamiques (Pompier, Secours, Crise, etc.)
- Messages **embarqués** chargés depuis `data/presets.json` à chaque ouverture
- Compléments éventuels en `localStorage` (navigateur)
- **+ Nouveau** : créer un message (Visu, Option, canal, texte)
- **Intégrer dans l'app** : enregistre vos prédéfinis actuels dans `data/presets.json` (visibles pour tous les navigateurs / après effacement du cache)
- **Ajouter / Modifier / Supprimer** : gérer les rubriques (rechargement page)
- Clic sur un bouton prédéfini → envoi sur le canal configuré (si connecté)
- Option cochée → modale pour compléter le texte avant envoi

Limite : **200 octets UTF-8** par message (compteur affiché).

## Colonne centrale — Messages

Fil des messages reçus (texte, canal, expéditeur).

## Colonne centrale — Message au clavier

### Groupe

- Choix du canal
- Texte + **Envoyer** (broadcast)

### Direct

- Sélection d’un nœud (liste à droite ou menu déroulant)
- Message sur **canal 0** (Fr_Balise / primaire) — chiffrement **PKI** côté mesh (Meshtastic 2.5+)
- Downlink via **JSON sendtext** uniquement (`to` + `hopLimit`) — pas le protobuf canal Fr_Balise
- **Envoyer direct**
- Journal serveur : `↑ JSON sendtext DM … → !node` — confirmer la réception **sur le Tag LoRa**, pas l’écho MQTT `[PKI]` dans le fil

## Colonne centrale — Info Routes 42

Zone **Internet** (seul appel externe). Voir [inforoute42.md](inforoute42.md).

**Carte** : bouton en-tête → [cartographie.md](cartographie.md) (toujours disponible ; signalements Inforoute si la case est cochée).

Activer / désactiver la zone **Remontée Info Routes 42** : case **Info Routes 42** en en-tête (voir [configuration.md](configuration.md)).

## Colonne droite — Nœuds

Liste des nœuds vus sur le mesh. Clic = sélection pour message direct.

## Limites Meshtastic

- Messages texte : **200 octets UTF-8**
- Waypoint : nom 30 car., description 100 car., expiration 24 h par défaut

## Raccourcis Info Routes (signalements)

| Action | Effet |
|--------|--------|
| Clic sur le signalement | Texte → **D_Ligerien** |
| Ctrl+clic (Cmd+clic Mac) | Waypoint → **canal 0** |
| Bouton **Message → D_Ligerien** | Idem clic |
| Bouton **📍 Repère → canal 0** | Idem Ctrl+clic |

## Persistance offline

Sans serveur : config et prédéfinis restent en localStorage ; connexion et envoi nécessitent l’API locale.

## Actualisation Info Routes

Automatique **toutes les 30 minutes** + bouton **Actualiser** manuel.
