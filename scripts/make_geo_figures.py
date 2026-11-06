"""Maps of Thailand and its night lights for the paper (Section 3.3).

Real data, unlike the synthetic panel: NASA Earth Observatory's Black Marble 2012 and 2016 global
grayscale composites (3 km, public domain) and geoBoundaries ADM1 province boundaries
(OpenStreetMap contributors, ODbL). Downloads go to data/raw/geo/ (not committed); outputs are
paper/figures/fig_map_thailand.png, fig_lights_thailand.png, fig_lights_bkk_eec.png, fig_lights_share.png,
paper/figures/geo_summary.json, whose numbers fill the {{geo:...}} placeholders in paper.md, the per-province
table paper/figures/geo_provinces.csv, and the
README banner docs/assets/banner.png.

The composites are 8-bit images scaled for display, not calibrated radiance: brightness sums are
used here only to describe where light is, never as a model input.

Usage: ``python scripts/make_geo_figures.py`` (or ``make geo``).
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import patheffects  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Patch, PathPatch  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402
from PIL import Image  # noqa: E402
from scipy.ndimage import gaussian_filter, zoom  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "geo"
FIG = ROOT / "paper" / "figures"
NASA = "https://assets.science.nasa.gov/content/dam/science/esd/eo/images/imagerecords/144000"
SOURCES = {
    "BlackMarble_2012_3km_gray_geo.tif": f"{NASA}/144896/BlackMarble_2012_3km_gray_geo.tif",
    "BlackMarble_2016_3km_gray_geo.tif": f"{NASA}/144897/BlackMarble_2016_3km_gray_geo.tif",
    "geoBoundaries-THA-ADM1_simplified.geojson": "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/"
    "releaseData/gbOpen/THA/ADM1/geoBoundaries-THA-ADM1_simplified.geojson",
}
BBOX = (97.0, 106.0, 5.3, 20.8)  # lon_min, lon_max, lat_min, lat_max
BMR = ["Bangkok", "Nonthaburi", "Pathum Thani", "Samut Prakan", "Samut Sakhon", "Nakhon Pathom"]
EEC = ["Chachoengsao", "Chon Buri", "Rayong"]
NO2_AREA = EEC + ["Samut Prakan"]  # config/indicators.yaml: no2 = EEC + Samut Prakan
CITIES = {  # label: (lon, lat, dx, dy) with the label offset in degrees
    "Bangkok": (100.50, 13.75, -2.2, 0.35),
    "Eastern Seaboard": (101.05, 12.95, 0.5, -0.65),
    "Chiang Mai": (98.98, 18.79, -1.9, 0.35),
    "Khon Kaen": (102.83, 16.43, 0.3, 0.25),
    "Nakhon Ratchasima": (102.10, 14.97, 0.35, 0.15),
    "Udon Thani": (102.79, 17.41, 0.3, 0.25),
    "Phuket": (98.39, 7.88, -0.2, -0.75),
    "Hat Yai": (100.47, 7.01, 0.4, -0.1),
}


ZOOM_PLACES = {  # label positions for the Bangkok / Eastern Seaboard zoom
    "Bangkok": (100.30, 13.62),
    "Ayutthaya": (100.57, 14.45),
    "Saraburi": (100.95, 14.62),
    "Chachoengsao": (101.35, 13.62),
    "Chon Buri": (101.35, 13.25),
    "Pattaya": (101.20, 12.86),
    "Rayong": (101.62, 12.55),
    "Gulf of Thailand": (100.45, 12.75),
}
DX = 360.0 / 13500  # Black Marble 3 km grid, from the GeoTIFF's ModelPixelScale tag
NIGHT_SEA = "#03060d"
NIGHT_LAND = np.array([0.055, 0.085, 0.15])
CITY_LIGHT = LinearSegmentedColormap.from_list(
    "city_light", ["#000000", "#3a1c05", "#b0560f", "#f5a623", "#ffe8a3", "#ffffff"]
)


def night_rgb(arr: np.ndarray, thai: np.ndarray, up: int = 4, glow_gain: float = 1.0) -> np.ndarray:
    """Brightness (0-255) -> RGB with a soft glow: upsampled, blurred at two scales and added back,
    on dark-blue land and a near-black sea; lights outside Thailand dimmed."""
    a = zoom(arr / 255.0, up, order=1)
    land = zoom(thai.astype(float), up, order=1)
    a = a * (0.2 + 0.8 * land)
    glow = glow_gain * (0.9 * gaussian_filter(a, 1.0 * up) + 0.6 * gaussian_filter(a, 3.5 * up))
    v = np.clip(0.85 * a + glow, 0, 1) ** (0.85 if glow_gain >= 1 else 1.3)
    sea = np.array(matplotlib.colors.to_rgb(NIGHT_SEA))
    base = sea + (NIGHT_LAND - sea) * gaussian_filter(land, 0.6 * up)[..., None]
    alpha = np.clip(v * 2.2, 0, 1)[..., None]
    return np.clip(base * (1 - alpha) + CITY_LIGHT(v)[..., :3] * alpha, 0, 1)


def fetch() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        if not (RAW / name).exists():
            print("downloading", url)
            req = urllib.request.Request(url, headers={"User-Agent": "thainowcast"})
            (RAW / name).write_bytes(urllib.request.urlopen(req, timeout=300).read())


def province_name(raw: str) -> str:
    return raw.removesuffix(" Province")


def load_provinces() -> dict[str, list[np.ndarray]]:
    gj = json.loads((RAW / "geoBoundaries-THA-ADM1_simplified.geojson").read_text(encoding="utf-8"))
    out: dict[str, list[np.ndarray]] = {}
    for f in gj["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        out[province_name(f["properties"]["shapeName"])] = [np.asarray(p[0]) for p in polys]  # outer rings
    assert len(out) == 77, len(out)
    return out


def load_lights(year: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Crop of the global equirectangular composite: (brightness 0-255, lon centres, lat centres)."""
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(RAW / f"BlackMarble_{year}_3km_gray_geo.tif")
    w, h = im.size
    dx, dy = 360.0 / w, 180.0 / h
    lon0, lon1, lat0, lat1 = BBOX
    c0, c1 = int((lon0 + 180) / dx), int(np.ceil((lon1 + 180) / dx))
    r0, r1 = int((90 - lat1) / dy), int(np.ceil((90 - lat0) / dy))
    arr = np.asarray(im.crop((c0, r0, c1, r1)))
    arr = arr[..., 0] if arr.ndim == 3 else arr
    lons = -180 + (np.arange(c0, c1) + 0.5) * dx
    lats = 90 - (np.arange(r0, r1) + 0.5) * dy
    return arr.astype(float), lons, lats


def masks(provinces: dict[str, list[np.ndarray]], lons: np.ndarray, lats: np.ndarray) -> dict[str, np.ndarray]:
    glon, glat = np.meshgrid(lons, lats)
    pts = np.column_stack([glon.ravel(), glat.ravel()])
    out = {}
    for name, rings in provinces.items():
        m = np.zeros(len(pts), bool)
        for ring in rings:
            lo, hi = ring.min(0), ring.max(0)
            cand = np.all((pts >= lo) & (pts <= hi), axis=1)
            m[cand] |= MPath(ring).contains_points(pts[cand])
        out[name] = m.reshape(glon.shape)
    return out


def draw_provinces(ax, provinces, face="none", edge="0.6", lw=0.3, only=None, **kw) -> None:
    for name, rings in provinces.items():
        if only is not None and name not in only:
            continue
        for ring in rings:
            ax.add_patch(PathPatch(MPath(ring), facecolor=face, edgecolor=edge, lw=lw, **kw))


def frame(ax, aspect: float) -> None:
    ax.set_xlim(BBOX[0], BBOX[1])
    ax.set_ylim(BBOX[2], BBOX[3])
    ax.set_aspect(aspect)
    ax.set_xticks(range(98, 106, 2))
    ax.set_yticks(range(6, 21, 2))
    ax.set_xticklabels([f"{x}°E" for x in range(98, 106, 2)], fontsize=7)
    ax.set_yticklabels([f"{y}°N" for y in range(6, 21, 2)], fontsize=7)


def label_cities(ax, color: str) -> None:
    for name, (lon, lat, ox, oy) in CITIES.items():
        ax.plot(lon, lat, "o", ms=2.5, color=color, mec="none")
        ax.annotate(name, (lon, lat), (lon + ox, lat + oy), fontsize=6.5, color=color,
                    arrowprops=dict(arrowstyle="-", lw=0.4, color=color))


def main() -> None:
    fetch()
    provinces = load_provinces()
    aspect = 1 / np.cos(np.deg2rad(13.0))  # equirectangular at Thailand's mid-latitude
    lights = {y: load_lights(y) for y in (2012, 2016)}
    _, lons, lats = lights[2016]
    m = masks(provinces, lons, lats)
    weight = np.cos(np.deg2rad(lats))[:, None] * np.ones_like(lights[2016][0])  # pixel area ~ cos(lat)
    thai = np.any(np.stack(list(m.values())), axis=0)

    # Figure: map of provinces and the areas named in the data section
    fig, ax = plt.subplots(figsize=(4.6, 6.2))
    draw_provinces(ax, provinces, face="#e9edf2", edge="white", lw=0.5)
    draw_provinces(ax, provinces, face="#f2a541", edge="white", lw=0.5, only=NO2_AREA)
    draw_provinces(ax, provinces, face="#1f3f6e", edge="white", lw=0.5, only=["Bangkok"])
    draw_provinces(ax, provinces, face="none", edge="#1f3f6e", lw=0.9, only=BMR)
    label_cities(ax, "0.15")
    frame(ax, aspect)
    ax.legend(handles=[Patch(fc="#1f3f6e", label="Bangkok"),
                       Patch(fc="none", ec="#1f3f6e", label="Bangkok Metropolitan Region"),
                       Patch(fc="#f2a541", label="NO2 area: EEC + Samut Prakan"),
                       Patch(fc="#e9edf2", ec="0.7", label="other provinces (77 in total)")],
              loc="lower left", fontsize=6.5, frameon=False)
    ax.set_title("Thailand: provinces and areas used in the data", fontsize=9)
    ax.text(0.99, 0.005, "Boundaries: geoBoundaries ADM1, © OpenStreetMap contributors (ODbL)",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=5, color="0.4")
    fig.tight_layout()
    fig.savefig(FIG / "fig_map_thailand.png", dpi=200)
    plt.close(fig)

    extent = (lons[0] - DX / 2, lons[-1] + DX / 2, lats[-1] - DX / 2, lats[0] + DX / 2)
    credit = "NASA Earth Observatory Black Marble (3 km grayscale composite) · boundaries © OpenStreetMap contributors"

    # Figure: Thailand at night, 2016 (the full country)
    rgb_2016 = night_rgb(lights[2016][0], thai)
    fig = plt.figure(figsize=(5.6, 8.0), facecolor=NIGHT_SEA)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.imshow(rgb_2016, extent=extent, interpolation="bilinear")
    draw_provinces(ax, provinces, edge="#6f8fbf", lw=0.25, alpha=0.18)
    for name, (lon, lat, ox, oy) in CITIES.items():
        ax.annotate(name, (lon, lat), (lon + ox, lat + oy), fontsize=7, color="#e8eefc", alpha=0.9,
                    arrowprops=dict(arrowstyle="-", lw=0.4, color="#e8eefc", alpha=0.6))
    ax.set_xlim(BBOX[0], BBOX[1])
    ax.set_ylim(BBOX[2], BBOX[3])
    ax.set_aspect(aspect)
    ax.axis("off")
    ax.text(0.56, 0.36, "Thailand\nat night", transform=ax.transAxes, fontsize=17, color="#f5f7ff",
            va="top", linespacing=1.0)
    ax.text(0.56, 0.285, "2016. Each glow is a town, a city,\na port or an industrial estate.",
            transform=ax.transAxes, fontsize=7.5, color="#9fb0d0", va="top")
    ax.text(0.98, 0.008, credit, transform=ax.transAxes, fontsize=5, color="#7d8db0", ha="right", va="bottom")
    fig.savefig(FIG / "fig_lights_thailand.png", dpi=220, facecolor=NIGHT_SEA)
    plt.close(fig)

    # README banner: the same night image beside the project name (docs/assets/banner.png)
    fig = plt.figure(figsize=(14, 5.2), facecolor=NIGHT_SEA)
    ax = fig.add_axes((0.02, 0.03, 0.28, 0.94))
    ax.imshow(rgb_2016, extent=extent, interpolation="bilinear")
    ax.set_xlim(BBOX[0], BBOX[1])
    ax.set_ylim(BBOX[2], BBOX[3])
    ax.set_aspect(aspect)
    ax.axis("off")
    fig.text(0.35, 0.64, "thainowcast", fontsize=46, fontweight="bold", color="#f5a623", va="center")
    fig.text(0.352, 0.43, "Pseudo-real-time nowcasting of Thai GDP and inflation\nfrom official statistics and alternative data",
             fontsize=15, color="#e8eefc", va="center", linespacing=1.4)
    fig.text(0.352, 0.25, "Google Trends · nighttime lights · Sentinel-5P NO2 · online prices · mobility",
             fontsize=11, color="#9fb0d0", va="center")
    fig.text(0.985, 0.04, "Thailand at night, 2016 · " + credit, fontsize=7, color="#7d8db0", ha="right")
    fig.savefig(ROOT / "docs" / "assets" / "banner.png", dpi=120, facecolor=NIGHT_SEA)
    plt.close(fig)

    # Figure: Bangkok and the Eastern Seaboard, 2012 and 2016
    zoom = (99.6, 102.0, 12.3, 15.0)
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 4.6), facecolor=NIGHT_SEA)
    for ax, year in zip(axes, (2012, 2016)):
        ax.imshow(night_rgb(lights[year][0], thai, glow_gain=0.35), extent=extent, interpolation="bilinear")
        draw_provinces(ax, provinces, edge="#6f8fbf", lw=0.35, alpha=0.3)
        for name, (lon, lat) in ZOOM_PLACES.items():
            ax.text(lon, lat, name, fontsize=6.5, color="white", ha="center",
                    path_effects=[patheffects.withStroke(linewidth=1.8, foreground="black")])
        ax.set_xlim(zoom[0], zoom[1])
        ax.set_ylim(zoom[2], zoom[3])
        ax.set_aspect(aspect)
        ax.axis("off")
        ax.set_title(str(year), color="#f5f7ff", fontsize=10)
    fig.text(0.5, 0.015, credit, ha="center", fontsize=5, color="#7d8db0")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(FIG / "fig_lights_bkk_eec.png", dpi=220, facecolor=NIGHT_SEA)
    plt.close(fig)

    # Shares of national light and land area by province
    area = {p: float((weight * mk).sum()) for p, mk in m.items()}
    total_area = sum(area.values())
    share = {}
    for year in (2012, 2016):
        arr = lights[year][0]
        light = {p: float((arr * weight * mk).sum()) for p, mk in m.items()}
        tot = sum(light.values())
        share[year] = {p: 100 * v / tot for p, v in light.items()}
    area_share = {p: 100 * v / total_area for p, v in area.items()}
    top = sorted(share[2016], key=share[2016].get, reverse=True)[:15]

    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    y = np.arange(len(top))[::-1]
    ax.barh(y, [share[2016][p] for p in top], color="#f2a541", label="share of national light, 2016")
    ax.plot([share[2012][p] for p in top], y, "|", ms=9, mew=1.6, color="#7a4a00", label="share of national light, 2012")
    ax.plot([area_share[p] for p in top], y, "o", ms=4, mfc="white", mec="#1f3f6e", label="share of land area")
    ax.set_yticks(y)
    ax.set_yticklabels(top, fontsize=7.5)
    ax.set_xlabel("percent of Thailand's total", fontsize=8)
    ax.tick_params(axis="x", labelsize=7.5)
    ax.legend(fontsize=7, frameon=False, loc="lower right")
    ax.set_title("Where Thailand's night light is: the 15 brightest provinces", fontsize=9)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG / "fig_lights_share.png", dpi=200)
    plt.close(fig)

    def group(d: dict[str, float], names: list[str]) -> float:
        return sum(d[p] for p in names)

    bkk = m["Bangkok"]
    summary = {
        "share_bkk_2016": group(share[2016], ["Bangkok"]),
        "share_bkk_2012": group(share[2012], ["Bangkok"]),
        "area_bkk": area_share["Bangkok"],
        "share_bmr_2016": group(share[2016], BMR),
        "area_bmr": group(area_share, BMR),
        "share_eec_2016": group(share[2016], EEC),
        "area_eec": group(area_share, EEC),
        "share_top10_2016": sum(sorted(share[2016].values(), reverse=True)[:10]),
        "saturated_bkk_2016": 100 * float((lights[2016][0][bkk] >= 255).mean()),
        "dark_land_2016": 100 * float((lights[2016][0][thai] < 10).mean()),
        "n_provinces": len(provinces),
    }
    (FIG / "geo_summary.json").write_text(json.dumps({k: round(v, 1) for k, v in summary.items()}, indent=2) + "\n",
                                          encoding="utf-8")
    # the per-province table behind Figure 6, for the Hugging Face dataset
    rows = ["province,land_share_pct,light_share_2012_pct,light_share_2016_pct,saturated_pixels_2016_pct"]
    for p in sorted(m, key=share[2016].get, reverse=True):
        sat = 100 * float((lights[2016][0][m[p]] >= 255).mean())
        rows.append(f"{p},{area_share[p]:.4f},{share[2012][p]:.4f},{share[2016][p]:.4f},{sat:.2f}")
    (FIG / "geo_provinces.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(json.dumps({k: round(v, 1) for k, v in summary.items()}, indent=2))


if __name__ == "__main__":
    main()
