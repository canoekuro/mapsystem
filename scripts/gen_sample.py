"""
Generate data/master.csv with sample store-facility combinations.
Covers 3 companies x 3-4 stores in the Nagoya area.
Each store has 8-15 facilities scattered within ~6km radius.
"""

import math
import os
import random

import pandas as pd

random.seed(42)

# ---------------------------------------------------------------------------
# Haversine distance (km) — standard library only
# ---------------------------------------------------------------------------

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in km between two WGS84 points."""
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Master data definition
# ---------------------------------------------------------------------------

COMPANIES = [
    {
        "company": "ヨークベニマル",
        "format": "SM",
        "stores": [
            {"code": "R001", "name": "ヨークベニマル名古屋中村店", "lat": 35.1705, "lon": 136.8816,
             "address": "愛知県名古屋市中村区名駅南一丁目1-1"},
            {"code": "R002", "name": "ヨークベニマル名古屋熱田店", "lat": 35.1238, "lon": 136.8997,
             "address": "愛知県名古屋市熱田区神宮三丁目2-5"},
            {"code": "R003", "name": "ヨークベニマル名古屋緑店", "lat": 35.0902, "lon": 136.9731,
             "address": "愛知県名古屋市緑区大高町字丸根1-1"},
        ],
    },
    {
        "company": "アピタ",
        "format": "GMS",
        "stores": [
            {"code": "R004", "name": "アピタ千代田橋店", "lat": 35.1543, "lon": 136.8722,
             "address": "愛知県名古屋市中川区千代田五丁目3-20"},
            {"code": "R005", "name": "アピタ名古屋北店", "lat": 35.2301, "lon": 136.9218,
             "address": "愛知県名古屋市北区楠味鋺一丁目510"},
            {"code": "R006", "name": "アピタ長久手店", "lat": 35.1812, "lon": 137.0443,
             "address": "愛知県長久手市砂子一丁目1101"},
            {"code": "R007", "name": "アピタ大府店", "lat": 35.0023, "lon": 136.9694,
             "address": "愛知県大府市江端町一丁目1"},
        ],
    },
    {
        "company": "イオン",
        "format": "GMS",
        "stores": [
            {"code": "R008", "name": "イオン名古屋茶屋店", "lat": 35.1891, "lon": 136.9502,
             "address": "愛知県名古屋市守山区小幡中三丁目3-1"},
            {"code": "R009", "name": "イオン熱田店", "lat": 35.1150, "lon": 136.8882,
             "address": "愛知県名古屋市熱田区川並町2-1"},
            {"code": "R010", "name": "イオン春日井店", "lat": 35.2488, "lon": 136.9718,
             "address": "愛知県春日井市柏原町一丁目1-1"},
        ],
    },
]

FACILITY_TYPES = ["保育園", "幼稚園", "こども園"]

FACILITY_TYPE_WEIGHTS = [0.45, 0.30, 0.25]

FACILITY_NAME_PREFIXES = [
    "さくら", "ひまわり", "たんぽぽ", "あおぞら", "にじ", "ほし", "つくし", "やまびこ",
    "みどり", "ふじ", "すみれ", "もも", "ちどり", "あすか", "なかよし", "きぼう",
    "ゆめ", "いずみ", "はな", "みなみ", "あかね", "しらゆき", "かわせみ",
]

DISTRICT_NAMES = [
    "中村区", "中川区", "熱田区", "緑区", "北区", "守山区", "東区", "西区",
    "南区", "瑞穂区", "千種区", "天白区", "昭和区", "名東区", "港区",
]


def random_facility_name(ftype: str, used: set) -> str:
    """Generate a unique facility name for the given type."""
    for _ in range(200):
        prefix = random.choice(FACILITY_NAME_PREFIXES)
        name = f"{prefix}{ftype}"
        if name not in used:
            used.add(name)
            return name
    # Fallback: append a counter
    idx = len(used)
    name = f"第{idx + 1}{ftype}"
    used.add(name)
    return name


def random_offset_km(min_km: float, max_km: float):
    """Return (dlat_deg, dlon_deg) representing a random displacement."""
    # Random angle and distance
    angle = random.uniform(0, 2 * math.pi)
    dist = random.uniform(min_km, max_km)
    # Approx degrees: 1 deg lat ~ 111 km, 1 deg lon ~ 91 km near 35N
    dlat = (dist * math.cos(angle)) / 111.0
    dlon = (dist * math.sin(angle)) / 91.0
    return dlat, dlon


def generate_facility_address(lat: float, lon: float) -> str:
    district = random.choice(DISTRICT_NAMES)
    chome = random.randint(1, 5)
    ban = random.randint(1, 20)
    go = random.randint(1, 15)
    return f"愛知県名古屋市{district}{chome}丁目{ban}-{go}"


# ---------------------------------------------------------------------------
# Build rows
# ---------------------------------------------------------------------------

rows = []
used_names: set = set()

for company_info in COMPANIES:
    company = company_info["company"]
    fmt = company_info["format"]
    for store in company_info["stores"]:
        code = store["code"]
        store_name = store["name"]
        store_lat = store["lat"]
        store_lon = store["lon"]
        store_address = store["address"]

        n_facilities = random.randint(14, 24)

        for _ in range(n_facilities):
            # Bias toward near facilities so a default 2km radius shows several
            # cards (and some stores overflow the PNG list -> "他 N 件"),
            # while keeping a tail beyond typical radii for filter coverage.
            roll = random.random()
            if roll < 0.70:
                # Within 0.2–2.0 km (inside the default radius)
                dlat, dlon = random_offset_km(0.2, 2.0)
            elif roll < 0.88:
                # 2.0–5.0 km (inside larger radius selections)
                dlat, dlon = random_offset_km(2.0, 5.0)
            else:
                # Beyond 5 km up to 8 km (outside some radius selections)
                dlat, dlon = random_offset_km(5.0, 8.0)

            fac_lat = round(store_lat + dlat, 6)
            fac_lon = round(store_lon + dlon, 6)

            ftype = random.choices(FACILITY_TYPES, weights=FACILITY_TYPE_WEIGHTS, k=1)[0]
            fac_name = random_facility_name(ftype, used_names)
            fac_address = generate_facility_address(fac_lat, fac_lon)

            dist_km = round(haversine(store_lat, store_lon, fac_lat, fac_lon), 1)

            rows.append(
                {
                    "企業名称": company,
                    "業態名称": fmt,
                    "小売店コード": code,
                    "小売店名称": store_name,
                    "店舗住所": store_address,
                    "店舗緯度": store_lat,
                    "店舗経度": store_lon,
                    "施設名称": fac_name,
                    "施設区分": ftype,
                    "施設住所": fac_address,
                    "施設緯度": fac_lat,
                    "施設経度": fac_lon,
                    "距離": dist_km,
                }
            )


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv("data/master.csv", index=False, encoding="utf-8")
    print(f"生成完了: {len(df)}行")
