# Tuiles OSM offline — France (zoom 6–10)

Tuiles raster pour fond de carte **sans Internet**, format `{z}/{x}/{y}.png`.

## Présentes sur GitHub (snapshot figé)

Les **~2 400 tuiles** sont **versionnées dans le dépôt** : après `git clone`, le dossier `OSM/` est complet.

- **Pas de téléchargement** en usage normal (`download_tiles.py` inutile après clone)
- **Pas de mise à jour OSM prévue** — snapshot France métropole + Corse, zoom 6–10
- Les commits / push **ultérieurs** ne modifient ces fichiers que si vous les changez volontairement

## Structure

```
OSM/
  6/32/22.png
  7/65/44.png
  ...
  download_tiles.py
  README.md
```

## Script `download_tiles.py` (optionnel)

Uniquement pour **régénérer** (autre zone, zoom, dossier vide) — pas l’usage courant :

```powershell
python OSM/download_tiles.py
```

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
