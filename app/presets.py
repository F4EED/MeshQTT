"""Messages prédéfinis embarqués (fichier data/presets.json)."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

PRESETS_PATH = Path(__file__).resolve().parent.parent / "data" / "presets.json"

DEFAULT_CATEGORIES: list[dict[str, str]] = [
    {"id": "pompier", "label": "Pompier"},
    {"id": "secours", "label": "Secours"},
    {"id": "secouriste", "label": "Secouriste"},
    {"id": "crise", "label": "Gestion de crise"},
    {"id": "communautaire", "label": "Communautaire"},
]

DEFAULT_PRESETS: dict[str, list[dict[str, Any]]] = {
    "pompier": [
        {"text": "Feu confirmé — renfort demandé", "channel": 0, "visu": "", "option": False},
        {"text": "Intervention terminée", "channel": 0, "visu": "", "option": False},
    ],
    "secours": [
        {"text": "Victime localisée", "channel": 0, "visu": "", "option": False},
        {"text": "Évacuation en cours", "channel": 0, "visu": "", "option": False},
    ],
    "secouriste": [
        {"text": "Premiers secours en cours", "channel": 0, "visu": "", "option": False},
        {"text": "Victime stabilisée", "channel": 0, "visu": "", "option": False},
    ],
    "crise": [
        {"text": "Cellule de crise activée", "channel": 0, "visu": "", "option": False},
        {"text": "Point de situation H+1", "channel": 0, "visu": "", "option": False},
    ],
    "communautaire": [
        {"text": "Hello from MeshQTT!", "channel": 0, "visu": "", "option": False},
        {"text": "Test ping mesh", "channel": 0, "visu": "", "option": False},
        {"text": "73", "channel": 0, "visu": "", "option": False},
    ],
}


def _normalize_message(item: Any) -> dict[str, Any] | None:
    if isinstance(item, str):
        text = item.strip()
        if not text:
            return None
        return {"text": text, "channel": 0, "visu": "", "option": False}
    if not isinstance(item, dict):
        return None
    text = str(item.get("text", "")).strip()
    if not text:
        return None
    channel = item.get("channel", 0)
    try:
        channel = max(0, min(7, int(channel)))
    except (TypeError, ValueError):
        channel = 0
    return {
        "text": text,
        "channel": channel,
        "visu": str(item.get("visu", "")).strip(),
        "option": bool(item.get("option", False)),
    }


def normalize_bundled_presets(data: dict[str, Any]) -> dict[str, Any]:
    categories_raw = data.get("categories")
    categories: list[dict[str, str]] = []
    if isinstance(categories_raw, list) and categories_raw:
        for cat in categories_raw:
            if not isinstance(cat, dict):
                continue
            cat_id = str(cat.get("id", "")).strip()
            label = str(cat.get("label", "")).strip()
            if cat_id and label:
                categories.append({"id": cat_id, "label": label})
    if not categories:
        categories = deepcopy(DEFAULT_CATEGORIES)

    presets_raw = data.get("presets")
    presets: dict[str, list[dict[str, Any]]] = {}
    known_ids = {c["id"] for c in categories}

    if isinstance(presets_raw, dict):
        for cat_id, messages in presets_raw.items():
            if cat_id not in known_ids or not isinstance(messages, list):
                continue
            normalized = []
            for item in messages:
                msg = _normalize_message(item)
                if msg:
                    normalized.append(msg)
            presets[cat_id] = normalized

    for cat in categories:
        presets.setdefault(cat["id"], [])

    return {"categories": categories, "presets": presets}


def default_bundled_presets() -> dict[str, Any]:
    return normalize_bundled_presets(
        {"categories": deepcopy(DEFAULT_CATEGORIES), "presets": deepcopy(DEFAULT_PRESETS)}
    )


def load_bundled_presets() -> dict[str, Any]:
    if not PRESETS_PATH.exists():
        return default_bundled_presets()
    try:
        stored = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
        return normalize_bundled_presets(stored)
    except (json.JSONDecodeError, OSError, ValueError, TypeError):
        return default_bundled_presets()


def save_bundled_presets(data: dict[str, Any]) -> dict[str, Any]:
    merged = normalize_bundled_presets(data)
    PRESETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PRESETS_PATH.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return merged
