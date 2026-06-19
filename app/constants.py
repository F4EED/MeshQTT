"""Constantes Meshtastic partagées."""

# Limite applicative des clients officiels (Android, iOS, Web) pour les messages
# texte. La charge utile LoRa est ~200 octets une fois chiffrement et en-têtes
# pris en compte — voir https://meshtastic.org/docs/overview/
MESH_TEXT_MESSAGE_MAX_BYTES = 200


def mesh_message_byte_length(text: str) -> int:
    return len(text.encode("utf-8"))


def validate_mesh_text_message(text: str) -> str:
    trimmed = text.strip()
    if not trimmed:
        raise ValueError("Message vide")
    nbytes = mesh_message_byte_length(trimmed)
    if nbytes > MESH_TEXT_MESSAGE_MAX_BYTES:
        raise ValueError(
            f"Message trop long ({nbytes}/{MESH_TEXT_MESSAGE_MAX_BYTES} octets UTF-8)"
        )
    return trimmed
