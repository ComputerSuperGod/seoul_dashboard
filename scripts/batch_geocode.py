import os, re
import pandas as pd
from app.utils_geocode import geocode_addresses
from app.settings import BASE_DIR

import sys, os
print("[DEBUG] Python 실행:", sys.executable)
print("[DEBUG] 현재 작업 디렉토리:", os.getcwd())
print("[DEBUG] batch_geocode.py 진입 완료")




CSV_PATH = BASE_DIR / "data" / "seoul_redev_projects.csv"

def build_full_address(gu: pd.Series, addr: pd.Series) -> pd.Series:
    def _norm(s: str) -> str:
        if not isinstance(s, str):
            return ""
        s = s.strip()
        s = re.sub(r"\(.*?\)", " ", s)
        s = re.sub(r"\b\d+\s*층\b", " ", s)
        s = re.sub(r"\b\d+\s*호\b", " ", s)
        s = s.replace(" 외", " ").replace("외 ", " ")
        s = re.sub(r"\s+", " ", s).strip()
        return s

    gu = gu.fillna("").astype(str).str.strip()
    addr = addr.fillna("").astype(str).map(_norm)

    full = []
    for g, a in zip(gu, addr):
        s = a
        if s and not s.startswith(("서울", "경기", "인천")):
            if g and not s.startswith(g):
                s = f"{g} {s}"
            s = f"서울특별시 {s}"
        full.append(s.strip())
    return pd.Series(full)

def main():
    df = pd.read_csv(CSV_PATH, encoding="cp949")
    # CSV 헤더 이름에 맞춰 가져오기
    gu = df["자치구"] if "자치구" in df.columns else pd.Series([""]*len(df))
    addr = None
    for c in ["정비구역위치", "대표지번", "address", "소재지", "지번주소", "도로명주소"]:
        if c in df.columns:
            addr = df[c]
            break
    if addr is None:
        addr = pd.Series([""] * len(df))

    addr_full = build_full_address(gu, addr)
    geocode_addresses(addr_full)
    print(f"✅ 지오코딩 캐시 업데이트 완료: {BASE_DIR / 'data' / 'geocode_cache.parquet'}")

if __name__ == "__main__":
    main()
