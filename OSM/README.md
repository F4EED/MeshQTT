# Tuiles OSM offline — France (zoom 6–10)

Tuiles raster pour fond de carte **sans Internet**, format `{z}/{x}/{y}.png`.

## Structure

```
OSM/
  6/32/22.png
  7/65/44.png
  ...
  download_tiles.py
```

Environ **2 400 tuiles** (~50 Mo) pour la France métropole + Corse, zoom 6 à 10.

## Téléchargement

Depuis la racine du projet :

```powershell
python OSM/download_tiles.py
```

Options utiles :

```powershell
python OSM/download_tiles.py --zoom-min 6 --zoom-max 10 --delay 0.25
python OSM/download_tiles.py --out D:\MonApp\OSM
```

Le script reprend là où il s’est arrêté (tuiles déjà présentes ignorées).

## Intégration Leaflet

```javascript
L.tileLayer('OSM/{z}/{x}/{y}.png', {
  minZoom: 6,
  maxZoom: 10,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
}).addTo(map);

map.setView([46.5, 2.5], 6);
```

Adapter le chemin selon comment l’app sert les fichiers statiques (`./OSM/…`, `/assets/OSM/…`, etc.).

## Attribution

Afficher la mention **© OpenStreetMap** dans l’application (obligatoire).

## Évolution

Pour plus de détail, relancer avec `--zoom-max 11` ou `12` (volume bien plus important).
