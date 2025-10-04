from pathlib import Path
import os
from dotenv import load_dotenv

# 프로젝트 루트: app/app.py에서 한 단계 위
BASE_DIR = Path(__file__).resolve().parents[1]

# .env 로드
load_dotenv(BASE_DIR / ".env")

KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "")
if not KAKAO_REST_API_KEY:
    # 키가 없어도 캐시만으로 동작 가능하되, 개발자에게만 경고
    print("⚠️  KAKAO_REST_API_KEY가 .env에 설정되어 있지 않습니다.")
