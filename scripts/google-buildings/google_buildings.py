import json
import pandas as pd
import geopandas as gpd
import pycountry
import s2geometry as s2
from shapely.geometry.polygon import Polygon

from pathlib import Path

from deepfacility.utils import spatial


updates = {
    'W. Sahara': 'Western Sahara',
    'Dem. Rep. Congo': 'Congo, The Democratic Republic of the',
    'Central African Rep.': 'Central African Republic',
    'Eq. Guinea': 'Equatorial Guinea',
    'Somaliland': 'Somalia',
    'S. Sudan': 'South Sudan',
    'eSwatini': 'Eswatini'
}


def s2token_to_polygon(s2_token: str) -> Polygon:
  s2_cell = s2.S2Cell(s2.S2CellId_FromToken(s2_token, len(s2_token)))
  s2s = [s2.S2LatLng(s2_cell.GetVertex(i)) for i in range(4)]
  xy = [(s.lng().degrees(), s.lat().degrees()) for s in s2s]
  return Polygon(xy)


def bounds_to_s2token(bounds: dict[str, float], level: int):
    s2_lat_lng_rect = s2.S2LatLngRect_FromPointPair(
        s2.S2LatLng_FromDegrees(bounds["miny"], bounds["minx"]),
        s2.S2LatLng_FromDegrees(bounds["maxy"], bounds["maxx"]))
    coverer = s2.S2RegionCoverer()
    coverer.set_fixed_level(level)
    cells = [cell.ToToken() for cell in coverer.GetCovering(s2_lat_lng_rect)]
    return cells


def gdf_to_s2tokens(gdf: gpd.GeoDataFrame, level: int):
    df = pd.concat([gdf.name, gdf.bounds], axis=1)
    country_bounds = df.set_index("name").to_dict(orient="index")
    s2tokens = {n: bounds_to_s2token(bs, level) for n, bs in country_bounds.items()}
    return s2tokens


def get_countries_gdf(continent: str = None, names: list = None):
    gdf = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))

    if continent:
        gdf = gdf[gdf.continent == continent]  # filter by continent

    if names and len(names) > 0:
        gdf = gdf[gdf.name.isin(names)]  # filter by country

    return gdf


def get_country_s2_tokens(continent: str = "Africa", names: list = None, level: int = 4):
    gdf = get_countries_gdf(continent, names)
    s2tokens = gdf_to_s2tokens(gdf, level)

    # Filter out those not in the country
    s2tokens_final = {}
    for name, s2ids in s2tokens.items():
        geom: Polygon = gdf[gdf["name"] == name][spatial.geom_col].iloc[0]
        assert geom, f"Country {name} shape is missing."
        name2 = updates[name] if name in updates else name
        s2tokens_final[name2] = {
            "code": pycountry.countries.lookup(name2).alpha_3,
            "s2": [t for t in s2ids if geom.intersects(s2token_to_polygon(t))]
        }

    return s2tokens_final


def main():
    country_s2_tokens = get_country_s2_tokens()
    filename = "../../src/deepfacility/config/countries_s2_tokens.json"
    Path(filename).parent.mkdir(exist_ok=True)
    with open(filename, 'w', encoding="utf-8") as fp:
        json.dump(country_s2_tokens, fp, indent=4)


if __name__ == "__main__":
    main()
