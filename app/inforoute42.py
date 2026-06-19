"""Récupération Inforoute 42 — https://www.inforoute42.fr/ (accès Internet)."""

from __future__ import annotations

import html
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

from app.constants import MESH_TEXT_MESSAGE_MAX_BYTES

INFOROUTE42_HOME_URL = "https://www.inforoute42.fr/"
INFOROUTE42_CONFIG_URL = (
    "https://www.inforoute42.fr/mod_turbolead/mod/inforoute/route.php?type=config"
)
INFOROUTE42_REPERE_URL = (
    "https://www.inforoute42.fr/mod_turbolead/mod/inforoute/route.php?type=repere"
)
INFOROUTE42_BARREAU_URL = (
    "https://www.inforoute42.fr/mod_turbolead/mod/inforoute/route.php?type=barreau"
)
INFOROUTE42_PHONE = "04 77 34 46 06"
USER_AGENT = "MeshQTT/1.0 (gestion de crise; usage local)"

EVENT_CATEGORY_ORDER = (
    "accident",
    "danger",
    "travaux",
    "gravillonnage",
    "autres",
    "deviation",
)

EVENT_CATEGORY_MESH_ABBR = {
    "accident": "Acc",
    "danger": "Dgr",
    "travaux": "Trav",
    "gravillonnage": "Grav",
    "autres": "Aut",
    "deviation": "Dev",
}

AUTRES_NOM_CLIPS = frozenset(
    {
        "BARRIERE_DE_DEGEL_12T",
        "BARRIERE_DE_DEGEL_7_5T",
        "BARRIERE_DE_DEGEL_7_5T_ET_12T",
        "CHRONOMETRE",
        "CIRCULATION_INTERDITE",
        "COL",
        "COL_EQUIPEMENTS_SPECIAUX",
        "COL_FERME",
        "FEU_ROUGE",
        "FLAGMAN",
        "KC1_BARRIERE_DE_DEGEL",
    }
)

DEVIATION_KEYWORDS = re.compile(
    r"d[ée]viation|d[ée]tour|ferm[ée]e|fermeture|route\s+coup[ée]e",
    re.I,
)

# Transformation affine point_xy → WGS84 (calibrée sur le fond carto Flash Inforoute 42).
# lat = _XY_TO_LAT_A * x + _XY_TO_LAT_B * y + _XY_TO_LAT_C
# lon = _XY_TO_LON_A * x + _XY_TO_LON_B * y + _XY_TO_LON_C
_XY_TO_LAT_A = -6.422050696199694e-05
_XY_TO_LAT_B = -0.0024524375483606087
_XY_TO_LAT_C = 46.296656389018
_XY_TO_LON_A = 0.001755861121416534
_XY_TO_LON_B = -4.59779748390194e-05
_XY_TO_LON_C = 3.694271746463484


def _html_to_text(raw: str) -> str:
    text = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"(?i)</li>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "• ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalize_teaser(raw: str) -> str:
    text = _html_to_text(raw)
    text = re.sub(r"\.{3}\s*$", "", text).strip()
    return re.sub(r"\s+", " ", text)


def _clamp_utf8(text: str, max_bytes: int) -> str:
    if len(text.encode("utf-8")) <= max_bytes:
        return text
    while text and len(text.encode("utf-8")) > max_bytes:
        text = text[:-1]
    return text.rstrip()


def _meaningful_bulletin_lines(bulletin_text: str) -> list[str]:
    lines: list[str] = []
    for ln in bulletin_text.splitlines():
        cleaned = ln.strip()
        if not cleaned:
            continue
        lower = cleaned.lower()
        if lower.startswith("pour plus d'informations"):
            break
        if "bonne route" in lower:
            continue
        if cleaned.startswith("•"):
            cleaned = cleaned[1:].strip()
        lines.append(cleaned)
    return lines


def _empty_events() -> dict[str, list[dict[str, Any]]]:
    return {key: [] for key in EVENT_CATEGORY_ORDER}


def _first_xy_token(raw: str) -> str:
    return (raw or "").strip().split()[0]


def _parse_xy(raw: str) -> tuple[float, float] | None:
    token = _first_xy_token(raw)
    if not token or ";" not in token:
        return None
    x_str, y_str = token.split(";", 1)
    try:
        return float(x_str), float(y_str)
    except ValueError:
        return None


def _parse_latlng(raw: str) -> tuple[float, float] | None:
    token = _first_xy_token(raw)
    if not token or ";" not in token:
        return None
    lat_str, lon_str = token.split(";", 1)
    try:
        return float(lat_str), float(lon_str)
    except ValueError:
        return None


def _latlon_from_xy(x: float, y: float) -> tuple[float, float]:
    lat = _XY_TO_LAT_A * x + _XY_TO_LAT_B * y + _XY_TO_LAT_C
    lon = _XY_TO_LON_A * x + _XY_TO_LON_B * y + _XY_TO_LON_C
    return lat, lon


def _geo_fields(parent: ET.Element) -> dict[str, Any]:
    point_xy = _text_or_empty(parent.find("point_xy"))
    point_latlng = _text_or_empty(parent.find("point_latlng"))
    fields: dict[str, Any] = {
        "point_xy": point_xy,
        "point_latlng": point_latlng,
        "latitude": None,
        "longitude": None,
        "latitude_from_xy": None,
        "longitude_from_xy": None,
    }

    latlng = _parse_latlng(point_latlng)
    if latlng is not None:
        fields["latitude"], fields["longitude"] = latlng

    xy = _parse_xy(point_xy)
    if xy is not None:
        fields["latitude_from_xy"], fields["longitude_from_xy"] = _latlon_from_xy(*xy)

    return fields


def _http_get(url: str, timeout: int = 20) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xml,text/xml,*/*",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.URLError as exc:
        raise ConnectionError(f"Inforoute 42 inaccessible : {exc}") from exc


def _load_repere_types(config_root: ET.Element) -> dict[str, dict[str, str]]:
    mapping: dict[str, dict[str, str]] = {}
    for node in config_root.findall("type_repere"):
        type_id = node.attrib.get("id", "")
        if not type_id:
            continue
        mapping[type_id] = {
            "nom": node.attrib.get("nom", ""),
            "nom_clip": node.attrib.get("nomClip", ""),
        }
    return mapping


def _categorize_repere_type(type_info: dict[str, str]) -> str:
    nom_clip = type_info.get("nom_clip", "").upper()
    nom = type_info.get("nom", "")
    nom_lower = nom.lower()

    if nom_clip == "ACCIDENT":
        return "accident"
    if nom_clip == "DANGER":
        return "danger"
    if nom_clip == "TRAVAUX":
        return "travaux"
    if nom_clip == "AK22" or "gravillon" in nom_lower:
        return "gravillonnage"
    if nom_clip in AUTRES_NOM_CLIPS:
        return "autres"
    return "autres"


def _text_or_empty(node: ET.Element | None) -> str:
    if node is None or node.text is None:
        return ""
    return node.text.strip()


def _event_from_repere(
    repere: ET.Element, type_map: dict[str, dict[str, str]]
) -> tuple[str, dict[str, str]]:
    type_id = repere.attrib.get("type", "")
    category = _categorize_repere_type(type_map.get(type_id, {}))
    period = ""
    start = repere.attrib.get("date_evt_debut", "").strip()
    end = repere.attrib.get("date_evt_fin", "").strip()
    if start or end:
        period = f"{start} → {end}".strip(" →")

    return category, {
        "title": _text_or_empty(repere.find("titre")),
        "description": _text_or_empty(repere.find("description")),
        "period": period,
        "road": "",
        **_geo_fields(repere),
    }


def _events_from_barreau(root: ET.Element) -> list[dict[str, str]]:
    deviations: list[dict[str, str]] = []
    seen: set[str] = set()

    for barreau in root.findall("barreau"):
        type_barreau = barreau.attrib.get("type_barreau", "")
        specific = _text_or_empty(barreau.find("commentaire_specifique"))
        is_deviation_type = "DEVIATION" in type_barreau.upper()
        is_deviation_text = bool(specific and DEVIATION_KEYWORDS.search(specific))

        if not is_deviation_type and not is_deviation_text:
            continue

        road = _text_or_empty(barreau.find("numero"))
        nom = _text_or_empty(barreau.find("nom"))
        circulation = _text_or_empty(barreau.find("circulation"))
        title = road or nom or "Alerte route"

        description_parts = [specific] if specific else []
        if circulation and circulation not in description_parts:
            description_parts.append(circulation)
        description = " — ".join(description_parts)

        key = f"{title}|{description}"
        if key in seen:
            continue
        seen.add(key)

        deviations.append(
            {
                "title": title,
                "description": description,
                "period": barreau.attrib.get("date_modif", "").strip(),
                "road": road,
                **_geo_fields(barreau),
            }
        )

    return deviations


def _fetch_map_events() -> dict[str, list[dict[str, Any]]]:
    events = _empty_events()
    config_root = ET.fromstring(_http_get(INFOROUTE42_CONFIG_URL))
    type_map = _load_repere_types(config_root)

    repere_root = ET.fromstring(_http_get(INFOROUTE42_REPERE_URL))
    for repere in repere_root.findall("repere"):
        category, event = _event_from_repere(repere, type_map)
        if not event["title"] and not event["description"]:
            continue
        events[category].append(event)

    barreau_root = ET.fromstring(_http_get(INFOROUTE42_BARREAU_URL, timeout=45))
    events["deviation"] = _events_from_barreau(barreau_root)

    for category in EVENT_CATEGORY_ORDER:
        events[category].sort(key=lambda item: item.get("title", "").lower())

    return events


def _build_mesh_summary(
    teaser: str,
    bulletin_text: str,
    events: dict[str, list[dict[str, str]]],
) -> str:
    count_parts: list[str] = []
    detail_parts: list[str] = []

    for category in EVENT_CATEGORY_ORDER:
        items = events.get(category, [])
        if not items:
            continue
        abbr = EVENT_CATEGORY_MESH_ABBR.get(category, category[:4])
        count_parts.append(f"{abbr}:{len(items)}")
        for event in items:
            title = (event.get("title") or event.get("description") or "").strip()
            if title:
                detail_parts.append(f"{abbr} {title}")

    if count_parts:
        msg = f"InfoR42 {' '.join(count_parts)}"
        if detail_parts:
            msg += " | " + " | ".join(detail_parts)
        return _clamp_utf8(msg, MESH_TEXT_MESSAGE_MAX_BYTES)

    lines = _meaningful_bulletin_lines(bulletin_text)
    headline = teaser or (lines[0] if lines else "")
    extras = [ln for ln in lines if ln != headline][:2]
    parts = [p for p in [headline, *extras] if p]
    body = " | ".join(parts) if parts else bulletin_text[:160]
    return _clamp_utf8(f"InfoR42: {body}", MESH_TEXT_MESSAGE_MAX_BYTES)


def _parse_homepage(page: str) -> dict[str, Any]:
    comment_match = re.search(
        r'id="commentaire-general"[^>]*>(.*?)</div>\s*<div',
        page,
        re.I | re.S,
    )
    if not comment_match:
        raise ValueError("Commentaire général absent de la page d'accueil")

    bulletin_html = comment_match.group(1).strip()
    if not bulletin_html:
        raise ValueError("Bulletin Inforoute 42 vide")

    teaser_match = re.search(
        r'class="BodyHeader-traffictxt">(.*?)</span>',
        page,
        re.I | re.S,
    )
    teaser = _normalize_teaser(teaser_match.group(1)) if teaser_match else ""

    updated_iso = None
    updated_display = None
    time_match = re.search(
        r'Mise à jour du site[^<]*(?:(?!</time>).)*<time[^>]*datetime="([^"]+)"[^>]*>([^<]+)</time>',
        page,
        re.I | re.S,
    )
    if time_match:
        updated_iso = time_match.group(1).strip()
        updated_display = html.unescape(time_match.group(2).strip())

    bulletin_text = _html_to_text(bulletin_html)
    lines = _meaningful_bulletin_lines(bulletin_text)

    return {
        "teaser": teaser,
        "updated_at": updated_display or updated_iso,
        "updated_at_display": updated_display,
        "updated_at_iso": updated_iso,
        "bulletin_text": bulletin_text,
        "bulletin_items": lines,
    }


def _parse_config_xml(payload: bytes) -> dict[str, Any]:
    root = ET.fromstring(payload)
    comment = root.find("commentaire_general")
    bulletin_html = "".join(comment.itertext()).strip() if comment is not None else ""
    if not bulletin_html:
        raise ValueError("Bulletin Inforoute 42 vide")

    updated_label = None
    for node in root.findall("date"):
        if node.attrib.get("type") == "last_comm_general":
            updated_label = (node.text or node.attrib.get("d") or "").strip() or None
            break

    bulletin_text = _html_to_text(bulletin_html)
    lines = _meaningful_bulletin_lines(bulletin_text)
    teaser = lines[0] if lines else _normalize_teaser(bulletin_html[:240])

    return {
        "teaser": teaser,
        "updated_at": updated_label,
        "updated_at_display": updated_label,
        "updated_at_iso": None,
        "bulletin_text": bulletin_text,
        "bulletin_items": lines,
    }


def fetch_inforoute42_bulletin() -> dict[str, Any]:
    """Bulletin + événements cartographiques (comme les filtres du site officiel)."""
    homepage = _http_get(INFOROUTE42_HOME_URL).decode("utf-8", errors="replace")
    try:
        core = _parse_homepage(homepage)
    except ValueError:
        payload = _http_get(INFOROUTE42_CONFIG_URL)
        try:
            core = _parse_config_xml(payload)
        except ET.ParseError as exc:
            raise ValueError("Réponse Inforoute 42 illisible") from exc

    events = _fetch_map_events()
    event_counts = {key: len(events[key]) for key in EVENT_CATEGORY_ORDER}

    return {
        "source": "inforoute42.fr",
        "source_url": INFOROUTE42_HOME_URL,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "updated_at": core.get("updated_at"),
        "updated_at_display": core.get("updated_at_display"),
        "updated_at_iso": core.get("updated_at_iso"),
        "teaser": core.get("teaser", ""),
        "bulletin_text": core.get("bulletin_text", ""),
        "bulletin_items": core.get("bulletin_items", []),
        "phone": INFOROUTE42_PHONE,
        "events": events,
        "event_counts": event_counts,
        "mesh_summary": _build_mesh_summary(
            core.get("teaser", ""),
            core.get("bulletin_text", ""),
            events,
        ),
    }
