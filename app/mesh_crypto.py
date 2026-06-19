"""Chiffrement / déchiffrement des paquets Meshtastic (AES-CTR)."""

import base64

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

try:
    from meshtastic.protobuf import mesh_pb2
except ImportError:
    from meshtastic import mesh_pb2


DEFAULT_KEY = "1PG7OiApB1nwvP+rz05pAQ=="


def xor_hash(data: bytes) -> int:
    result = 0
    for char in data:
        result ^= char
    return result


def generate_hash(name: str, key: str) -> int:
    replaced_key = key.replace("-", "+").replace("_", "/")
    key_bytes = base64.b64decode(replaced_key.encode("utf-8"))
    return xor_hash(name.encode("utf-8")) ^ xor_hash(key_bytes)


def normalize_key(key: str) -> str:
    if key in ("", "AQ=="):
        return DEFAULT_KEY
    return key


def decode_encrypted_packet(mp, key: str) -> bool:
    """Déchiffre mp.encrypted dans mp.decoded. Retourne True si succès."""
    try:
        key_bytes = base64.b64decode(normalize_key(key).encode("ascii"))
        nonce = mp.id.to_bytes(8, "little") + getattr(mp, "from").to_bytes(8, "little")
        cipher = Cipher(algorithms.AES(key_bytes), modes.CTR(nonce), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(mp.encrypted) + decryptor.finalize()
        data = mesh_pb2.Data()
        data.ParseFromString(decrypted)
        mp.decoded.CopyFrom(data)
        return True
    except Exception:
        return False


def try_decode_encrypted_packet(mp, keys: list[str]) -> bool:
    """Essaie chaque clé jusqu'à déchiffrement réussi."""
    if not keys:
        return False
    encrypted = mp.encrypted
    for key in keys:
        if not key:
            continue
        mp.decoded.Clear()
        mp.encrypted = encrypted
        if decode_encrypted_packet(mp, key):
            return True
    mp.decoded.Clear()
    mp.encrypted = encrypted
    return False


def encrypt_payload(
    channel: str,
    key: str,
    packet_id: int,
    from_node: int,
    encoded_message,
) -> tuple[int, bytes]:
    """Retourne (channel_hash, encrypted_bytes)."""
    norm_key = normalize_key(key)
    channel_hash = generate_hash(channel, norm_key)
    key_bytes = base64.b64decode(norm_key.encode("ascii"))
    nonce = packet_id.to_bytes(8, "little") + from_node.to_bytes(8, "little")
    cipher = Cipher(algorithms.AES(key_bytes), modes.CTR(nonce), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(encoded_message.SerializeToString()) + encryptor.finalize()
    return channel_hash, encrypted
