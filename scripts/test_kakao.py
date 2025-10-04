# scripts/test_kakao.py
from pathlib import Path
import sys, requests, os
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.settings import KAKAO_REST_API_KEY

print("KEY_EXISTS:", bool(KAKAO_REST_API_KEY), "LEN:", len(KAKAO_REST_API_KEY or ""))
url = "https://dapi.kakao.com/v2/local/search/address.json"
headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
params = {"query": "서울특별시 중구 세종대로 110"}
r = requests.get(url, headers=headers, params=params, timeout=5)
print("status:", r.status_code)
print("body:", r.text)  # ← 여기 메시지에 'insufficient permissions' 등 원인 나옵니다.
