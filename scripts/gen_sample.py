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
             "address": "愛知県名古屋市中村区名駅南一丁目1-1", "pref": "愛知県"},
            {"code": "R002", "name": "ヨークベニマル名古屋熱田店", "lat": 35.1238, "lon": 136.8997,
             "address": "愛知県名古屋市熱田区神宮三丁目2-5", "pref": "愛知県"},
            {"code": "R003", "name": "ヨークベニマル岐阜店", "lat": 35.0902, "lon": 136.9731,
             "address": "岐阜県岐阜市大高町字丸根1-1", "pref": "岐阜県"},
        ],
    },
    {
        "company": "アピタ",
        "format": "GMS",
        "stores": [
            {"code": "R004", "name": "アピタ千代田橋店", "lat": 35.1543, "lon": 136.8722,
             "address": "愛知県名古屋市中川区千代田五丁目3-20", "pref": "愛知県"},
            {"code": "R005", "name": "アピタ名古屋北店", "lat": 35.2301, "lon": 136.9218,
             "address": "愛知県名古屋市北区楠味鋺一丁目510", "pref": "愛知県"},
            {"code": "R006", "name": "アピタ長久手店", "lat": 35.1812, "lon": 137.0443,
             "address": "愛知県長久手市砂子一丁目1101", "pref": "愛知県"},
            {"code": "R007", "name": "アピタ桑名店", "lat": 35.0023, "lon": 136.9694,
             "address": "三重県桑名市江端町一丁目1", "pref": "三重県"},
        ],
    },
    {
        "company": "イオン",
        "format": "GMS",
        "stores": [
            {"code": "R008", "name": "イオン名古屋茶屋店", "lat": 35.1891, "lon": 136.9502,
             "address": "愛知県名古屋市守山区小幡中三丁目3-1", "pref": "愛知県"},
            {"code": "R009", "name": "イオン熱田店", "lat": 35.1150, "lon": 136.8882,
             "address": "愛知県名古屋市熱田区川並町2-1", "pref": "愛知県"},
            {"code": "R010", "name": "イオン四日市店", "lat": 35.2488, "lon": 136.9718,
             "address": "三重県四日市市柏原町一丁目1-1", "pref": "三重県"},
        ],
    },
]

# 推進園名称 の末尾に付く自然な語（表示名用）
FACILITY_NAME_SUFFIXES = ["保育園", "幼稚園", "こども園"]

FACILITY_TYPE_WEIGHTS = [0.45, 0.30, 0.25]

# 表示名の末尾語 → 実データの 推進園区分（色分けキー）
FACILITY_CATEGORY_BY_SUFFIX = {
    "保育園": "認可保育所",
    "幼稚園": "幼稚園",
    "こども園": "認定こども園",
}

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
        store_pref = store["pref"]

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

            suffix = random.choices(
                FACILITY_NAME_SUFFIXES, weights=FACILITY_TYPE_WEIGHTS, k=1
            )[0]
            fac_name = random_facility_name(suffix, used_names)
            category = FACILITY_CATEGORY_BY_SUFFIX[suffix]
            fac_address = generate_facility_address(fac_lat, fac_lon)

            dist_km = round(haversine(store_lat, store_lon, fac_lat, fac_lon), 1)

            rows.append(
                {
                    "企業名称": company,
                    "業態名称": fmt,
                    "店舗コード": code,
                    "店舗名称": store_name,
                    "店舗_都道府県": store_pref,
                    "店舗住所": store_address,
                    "店舗lat": store_lat,
                    "店舗lon": store_lon,
                    "推進園名称": fac_name,
                    "推進園区分": category,
                    "推進園_都道府県": store_pref,
                    "推進園住所": fac_address,
                    "推進園lat": fac_lat,
                    "推進園lon": fac_lon,
                    "距離km": dist_km,
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
