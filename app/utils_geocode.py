import re, time, requests
import pandas as pd
from pathlib import Path
from app.settings import KAKAO_REST_API_KEY, BASE_DIR

SESSION = requests.Session()
CACHE_DIR = BASE_DIR / "data"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_PATH = CACHE_DIR / "geocode_cache.parquet"

def _normalize_addr(addr: str) -> str:
    if not isinstance(addr, str): return ""
    s = addr.strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\(.*?\)", "", s).strip()
    return s

def _empty_cache():
    return pd.DataFrame(columns=["norm_addr","raw_addr","lon","lat","score","source","ts"])

def _load_cache() -> pd.DataFrame:
    if CACHE_PATH.exists():
        try:
            return pd.read_parquet(CACHE_PATH)
        except Exception:
            csv_path = CACHE_PATH.with_suffix(".csv")
            return pd.read_csv(csv_path) if csv_path.exists() else _empty_cache()
    return _empty_cache()

def _save_cache(df: pd.DataFrame):
    df.to_parquet(CACHE_PATH, index=False)
    df.to_csv(CACHE_PATH.with_suffix(".csv"), index=False, encoding="utf-8-sig")

def _kakao_geocode_one(addr: str, retries=2, sleep=0.25):
    """카카오 주소→좌표 변환 (재시도 + 타임아웃 + 로그)"""
    if not KAKAO_REST_API_KEY:
        print("[ERR] Kakao API key is missing.")
        return None

    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    params = {"query": addr}

    for attempt in range(retries + 1):
        try:
            r = SESSION.get(url, headers=headers, params=params, timeout=5)
            r.raise_for_status()

            j = r.json()
            docs = j.get("documents", [])
            if not docs:
                print(f"[WARN] No result for: {addr}")
                return None

            d0 = docs[0]
            lon = float(d0.get("x"))
            lat = float(d0.get("y"))
            score = 1.0 if d0.get("road_address") else 0.8

            return {"lon": lon, "lat": lat, "score": score, "source": "kakao"}

        except Exception as e:
            print(f"[ERR] geocode fail (attempt {attempt+1}/{retries+1}): {addr} -> {e}")
            time.sleep(sleep)

    return None

def geocode_addresses(addresses: pd.Series) -> pd.DataFrame:
    cache = _load_cache()
    seen = set(cache["norm_addr"].tolist())

    new_rows = []
    for raw in addresses.fillna(""):
        norm = _normalize_addr(raw)
        if not norm or norm in seen:
            continue
        res = _kakao_geocode_one(norm)
        if res is None:
            res = {"lon": None, "lat": None, "score": 0.0, "source": "kakao"}
        new_rows.append({
            "norm_addr": norm, "raw_addr": raw,
            **res, "ts": pd.Timestamp.utcnow()
        })
        time.sleep(0.25)

    if new_rows:
        upd = pd.concat([cache, pd.DataFrame(new_rows)], ignore_index=True)
        upd = upd.sort_values(["norm_addr","ts"]).drop_duplicates("norm_addr", keep="last")
        _save_cache(upd)
        return upd
    return cache

def map_addresses(df: pd.DataFrame, addr_col="address") -> pd.DataFrame:
    cache = _load_cache()
    out = df.copy()
    out["norm_addr"] = out[addr_col].map(_normalize_addr)
    out = out.merge(cache[["norm_addr","lon","lat","score"]], on="norm_addr", how="left")
    return out
