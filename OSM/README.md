# Tuiles OSM offline — France (zoom 6–10)

Tuiles raster pour fond de carte **sans Internet**, format `{z}/{x}/{y}.png`.

## Fichiers locaux (hors Git)

Les tuiles PNG **ne sont pas versionnées** : `git commit` / `git push` les ignore.  
Elles restent sur votre disque dans `OSM/` une fois générées — **pas de retéléchargement** tant que vous ne supprimez pas le dossier.

Après un `git clone` sur une autre machine, lancer **une seule fois** :

```powershell
python OSM/download_tiles.py
```

Snapshot prévu : France métropole + Corse, zoom 6–10 (~2 400 tuiles, ~16 Mo). **Pas de mise à jour OSM prévue.**

## Structure

```
OSM/
  6/32/22.png          # local uniquement (.gitignore)
  7/65/44.png
  ...
  download_tiles.py    # dans Git
  README.md            # dans Git
```

## Script `download_tiles.py`

```powershell
python OSM/download_tiles.py
```

Options :

```powershell
python OSM/download_tiles.py --zoom-min 6 --zoom-max 10 --delay 0.25
python OSM/download_tiles.py --out D:\MonApp\OSM
```

Tuiles déjà présentes = ignorées (reprise possible).

## Intégration Leaflet

```javascript
L.tileLayer('OSM/{z}/{x}/{y}.png', {
  minZoom: 6,
  maxZoom: 10,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
}).addTo(map);

map.setView([46.5, 2.5], 6);
```

## Attribution

Afficher la mention **© OpenStreetMap** dans l’application (obligatoire).
