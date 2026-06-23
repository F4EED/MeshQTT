#!/usr/bin/env python3
"""Télécharge des tuiles OSM pour usage offline (France, zoom 6-10 par défaut).

Structure produite : OSM/{z}/{x}/{y}.png

Usage :
    python OSM/download_tiles.py
    python OSM/download_tiles.py --zoom-min 6 --zoom-max 10 --delay 0.25

Politique OSM : usage personnel / offline uniquement, avec attribution dans l'app.
https://operations.osmfoundation.org/policies/tiles/
"""

from __future__ import annotations

import argparse
import math
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# France métropole + Corse
DEFAULT_BBOX = (-5.5, 41.3, 9.8, 51.1)  # ouest, sud, est, nord
TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
SUBDOMAINS = "abc"
USER_AGENT = "OfflineMapTiles/1.0 (usage offline personnel; https://www.openstreetmap.org/copyright)"


def deg2tile(lat: float, lon: float, z: int) -> tuple[int, int]:
    n = 2**z
    x = int((lon + 180) / 360 * n)
    lat_r = math.radians(lat)
    y = int((1 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r)) / math.pi) / 2 * n)
    return x, y


def tiles_for_bbox(west: float, south: float, east: float, north: float, z: int):
    x0, y_n = deg2tile(north, west, z)
    x1, y_s = deg2tile(south, east, z)
    x_min, x_max = min(x0, x1), max(x0, x1)
    y_min, y_max = min(y_n, y_s), max(y_n, y_s)
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            yield z, x, y


def download_tile(
    out_dir: Path,
    z: int,
    x: int,
    y: int,
    delay: float,
    retries: int,
) -> bool:
    path = out_dir / str(z) / str(x) / f"{y}.png"
    if path.exists() and path.stat().st_size > 0:
        return True

    path.parent.mkdir(parents=True, exist_ok=True)
    sub = SUBDOMAINS[(x + y) % len(SUBDOMAINS)]
    url = TILE_URL.format(s=sub, z=z, x=x, y=y)

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                path.write_bytes(resp.read())
            if delay > 0:
                time.sleep(delay)
            return True
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                print(f"  404 {z}/{x}/{y} — ignoré")
                return False
            if attempt + 1 < retries:
                time.sleep(delay * 4)
            else:
                print(f"  ERREUR HTTP {exc.code} {z}/{x}/{y}", file=sys.stderr)
                return False
        except OSError as exc:
            if attempt + 1 < retries:
                time.sleep(delay * 4)
            else:
                print(f"  ERREUR {z}/{x}/{y}: {exc}", file=sys.stderr)
                return False
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Télécharge tuiles OSM offline (France)")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Répertoire de sortie (défaut: OSM/)",
    )
    parser.add_argument("--zoom-min", type=int, default=6)
    parser.add_argument("--zoom-max", type=int, default=10)
    parser.add_argument("--west", type=float, default=DEFAULT_BBOX[0])
    parser.add_argument("--south", type=float, default=DEFAULT_BBOX[1])
    parser.add_argument("--east", type=float, default=DEFAULT_BBOX[2])
    parser.add_argument("--north", type=float, default=DEFAULT_BBOX[3])
    parser.add_argument(
        "--delay",
        type=float,
        default=0.25,
        help="Pause entre requêtes (s), respecter les serveurs OSM",
    )
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()

    if args.zoom_min < 0 or args.zoom_max > 19 or args.zoom_min > args.zoom_max:
        print("Plage de zoom invalide (0-19)", file=sys.stderr)
        return 1

    todo: list[tuple[int, int, int]] = []
    for z in range(args.zoom_min, args.zoom_max + 1):
        todo.extend(tiles_for_bbox(args.west, args.south, args.east, args.north, z))

    existing = sum(
        1
        for z, x, y in todo
        if (args.out / str(z) / str(x) / f"{y}.png").exists()
    )
    print(f"Tuiles à traiter : {len(todo)} ({existing} déjà présentes)")
    print(f"Sortie : {args.out.resolve()}")
    print(f"Zoom {args.zoom_min}–{args.zoom_max}, délai {args.delay}s\n")

    ok = skip = fail = 0
    for i, (z, x, y) in enumerate(todo, 1):
        path = args.out / str(z) / str(x) / f"{y}.png"
        if path.exists() and path.stat().st_size > 0:
            skip += 1
        elif download_tile(args.out, z, x, y, args.delay, args.retries):
            ok += 1
        else:
            fail += 1

        if i % 50 == 0 or i == len(todo):
            print(f"  [{i}/{len(todo)}] téléchargées={ok} existantes={skip} échecs={fail}")

    print(f"\nTerminé : {ok} téléchargées, {skip} déjà là, {fail} échecs")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
