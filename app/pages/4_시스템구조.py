# pages/4_시스템 구조.py
# 📦 AIoT 스마트 인프라 대시보드 — 시스템 구조 & 데이터 흐름 안내 페이지
# - 기존 "4사분면" 페이지를 대체하는 문서/가이드용 페이지
# - app.py와 동일한 톤/스타일 일부 차용

from __future__ import annotations
import sys
from pathlib import Path
import streamlit as st
import pandas as pd

# ────────────────────────────────────────────────────────────────
# 기본 설정 & 스타일
# ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="시스템 구조 | AIoT 스마트 인프라 대시보드", layout="wide")

st.markdown("""
<style>
.katex-display { text-align: left !important; margin-left: 0 !important; }
.block-container { text-align: left !important; }
div[data-testid="stMarkdownContainer"] .katex-display { text-align: left !important; margin-left: 0 !important; margin-right: auto !important; }
div[data-testid="stMarkdownContainer"] .katex-display > .katex { display: inline-block !important; }
div[data-testid="stMarkdownContainer"] p { text-align: left !important; margin-left: 0 !important; }
.small-muted { color: #7a7a7a; font-size: 0.9rem; }
.kpi-card { padding: 16px; border-radius: 16px; background: #111827; border: 1px solid #1f2937; }
.kpi-title { font-size: 0.9rem; color: #9ca3af; margin-bottom: 8px; }
.kpi-value { font-size: 1.2rem; font-weight: 700; color: #e5e7eb; }
.section-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 8px; }
hr.soft { border: none; height: 1px; background: #1f2937; margin: 16px 0; }
</style>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────────
# 경로 상수
# ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parents[1]  # repo root 추정
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"

# ────────────────────────────────────────────────────────────────
# 헤더
# ────────────────────────────────────────────────────────────────
st.title("🏗 AIoT 스마트 인프라 대시보드 — 시스템 구조")
st.caption("본 페이지는 개발자/운영자를 위한 **폴더 구조, 데이터 파이프라인, 캐시 전략, 확장 포인트**를 요약합니다.")

# 폴더 구조 이미지가 있으면 표시 (예: assets/structure.png)
img_candidates = [
    ASSETS_DIR / "structure.png",
    ASSETS_DIR / "folder-structure.png",
    ASSETS_DIR / "tree.png",
]
img_path = next((p for p in img_candidates if p.exists()), None)
if img_path:
    st.image(str(img_path), caption="프로젝트 폴더 구조 (assets 내 이미지 자동 탐색)")

# ────────────────────────────────────────────────────────────────
# 1) 전체 폴더 트리 & 역할
# ────────────────────────────────────────────────────────────────
st.markdown("### 1) 전체 폴더 트리")
st.code(f"""
{BASE_DIR.name}/
├─ app.py                        # 4사분면 메인 대시보드 (지도·링크혼잡·시나리오)
├─ data/                         # 원본/전처리 데이터 (CSV/XLSX/SHP 등)
│   ├─ seoul_redev_projects.csv
│   ├─ AverageSpeed(LINK).xlsx
│   ├─ AverageSpeed(LINK)_2023.csv
│   ├─ TrafficVolume_Seoul_2023.csv
│   └─ seoul_link_lev5.5_2023.shp
├─ utils/                        # 데이터 전처리·시각화 유틸
│   ├─ traffic_preproc.py        # ensure_speed_csv 등 CSV 변환/정제
│   └─ traffic_plot.py           # plot_speed / plot_nearby_speed_from_csv
├─ components/                   # UI 컴포넌트(사이드바 가이드/프리셋 등)
│   ├─ sidebar_presets.py
│   └─ sidebar_4quadrant_guide.py
├─ pages/                        # 문서/가이드 서브 페이지
│   └─ 4_시스템 구조.py          # (현재 페이지) 시스템 구조 가이드
└─ assets/                       # (선택) 문서 이미지·아이콘 등
""".strip(), language="text")

st.markdown("### 2) 모듈별 핵심 역할")
cols = st.columns(5)
with cols[0]:
    st.markdown("**`app.py`**")
    st.write("- 4사분면 UI 메인\n- 교통/지도/혼잡 계산\n- 시나리오·민감도·확률 탭")
with cols[1]:
    st.markdown("**`components/`**")
    st.write("- 사이드바 프리셋/가이드\n- 재사용 가능한 UI 블록")
with cols[2]:
    st.markdown("**`pages/`**")
    st.write("- 사용자/운영자 문서\n- 구조/가이드/릴리즈 노트 등")
with cols[3]:
    st.markdown("**`utils/`**")
    st.write("- 데이터 전처리/정제\n- 링크 속도 시각화 함수")
with cols[4]:
    st.markdown("**`data/`**")
    st.write("- 원천·전처리 산출물\n- Shapefile/CSV/XLSX")

st.divider()

# ────────────────────────────────────────────────────────────────
# 3) 데이터 파이프라인 & 캐시 전략
# ────────────────────────────────────────────────────────────────
st.markdown("### 3) 데이터 파이프라인")

st.markdown("""
1. **정비사업 원본 로드 → 정규화**
   - `load_raw_projects()` → `normalize_projects()`
   - 컬럼 스키마 통일, 수치형/범주형 최적화, 결측 보정
2. **좌표 병합**
   - `load_coords()`에서 `name+gu` 기준 좌표 병합
   - 좌표 누락 시 구(區) 중심 + jittering
3. **교통데이터 준비**
   - `utils.traffic_preproc.ensure_speed_csv(xlsx→csv)` (필요시 자동 변환)
   - `utils.traffic_plot.plot_speed(...)` 또는 fallback
4. **혼잡도 계산**
   - `compute_congestion_from_speed()`로 링크별 `혼잡도(%)` 계산
   - 일평균 혼잡도 집계 → 지도 GeoJSON 색상화
5. **지도 렌더링**
   - `_geojson_cache_store()/get()`으로 캐시에 GeoJSON 보관
   - `st.session_state`에는 **키만 저장** (메모리 절감)
""")

st.markdown("### 4) Streamlit 캐시 계층")
st.write("- `@st.cache_resource`: **대용량/변경 드문 리소스** (Shapefile, GeoDataFrame 등)")
st.write("- `@st.cache_data`: **가벼운 데이터/연산 결과** (CSV 로드, 전처리, 집계 등)")
st.write("- `st.session_state`: **UI 상태** 및 **GeoJSON 키**만 저장하여 객체 중복 보관 방지")

with st.container():
    st.markdown("#### 세션 키 요약")
    df_keys = pd.DataFrame([
        {"키": "matched_geo_key_daily", "설명": "일평균 혼잡 GeoJSON 캐시 키", "예시": "1250_41.3_abs"},
        {"키": "matched_geo_key_hourly","설명": "(미사용) 시간대 혼잡 GeoJSON 키", "예시": "-"},
        {"키": "color_mode_daily_val",  "설명": "지도 색 기준(절대/상대)", "예시": "절대(30/70)"},
        {"키": "selected_row",          "설명": "선택된 단지(테이블 인덱스)", "예시": "42"},
        {"키": "selected_gu_prev",      "설명": "이전 구(區) 선택 상태", "예시": "강남구"},
        {"키": "eta_by_gu",             "설명": "구별 혼잡 민감도 η", "예시": "{'강남구':0.75}"},
        {"키": "df_plot_all",           "설명": "반경 내 링크 속도 원본(3-2/3-3 공유)", "예시": "DataFrame"},
        {"키": "curve_33",              "설명": "기준/재건축후 혼잡 곡선(base/after)", "예시": "DataFrame"},
        {"키": "auto_defaults",         "설명": "3-4 탭 자동 기본값 번들", "예시": "{...}"},
        {"키": "df_scn_result",         "설명": "시나리오 비교 결과", "예시": "DataFrame"},
        {"키": "df_tornado",            "설명": "민감도(토네이도) 표", "예시": "DataFrame"},
        {"키": "mc_p10p50p90",          "설명": "몬테카를로 P10/P50/P90", "예시": "(..,..,..)"},
    ])
    st.dataframe(df_keys, use_container_width=True, hide_index=True)

st.divider()

# ────────────────────────────────────────────────────────────────
# 5) 주요 상수/경로 (app.py 기준)
# ────────────────────────────────────────────────────────────────
st.markdown("### 5) 주요 상수/경로")
rows = [
    ("BASE_YEAR", "기준년도", "2023"),
    ("PROJECTS_CSV_PATH", "정비사업 원본 CSV", "data/seoul_redev_projects.csv"),
    ("TRAFFIC_XLSX_PATH", "교통 속도 원본 XLSX", "data/AverageSpeed(LINK).xlsx"),
    ("TRAFFIC_CSV_PATH",  "교통 속도 CSV(생성)", "data/AverageSpeed(LINK)_2023.csv"),
    ("TRAFFIC_VOL_CSV_PATH", "교통 볼륨 CSV(선택)", "data/TrafficVolume_Seoul_2023.csv"),
    ("SHP_PATH", "링크 Shapefile", "data/seoul_link_lev5.5_2023.shp"),
    ("LINK_ID_COL", "Shapefile 링크 ID 컬럼", "k_link_id"),
]
st.table(pd.DataFrame(rows, columns=["상수", "의미", "예시 경로/값"]))

st.divider()

# ────────────────────────────────────────────────────────────────
# 6) 성능 최적화 체크리스트
# ────────────────────────────────────────────────────────────────
st.markdown("### 6) 성능 최적화 체크리스트")
st.markdown("""
- ✅ **캐시**: Shapefile → `@st.cache_resource`, CSV/집계 → `@st.cache_data`
- ✅ **세션 최소화**: 큰 객체 대신 **키**만 `st.session_state`에 저장
- ✅ **dtype 최적화**: `_downcast_numeric`, `_categorify`로 메모리 절감
- ✅ **재사용**: 공통 계산(혼잡 변환, 일평균, GeoJSON 빌드) 함수화
- ✅ **레이아웃 분리**: 지도/차트 렌더 블록을 분리해 불필요한 재계산 최소화
- ✅ **방어적 코딩**: 파일 부재/결측 시 안내 메시지·기본값 제공
""")

# ────────────────────────────────────────────────────────────────
# 7) 확장 포인트
# ────────────────────────────────────────────────────────────────
st.markdown("### 7) 확장 포인트")
st.markdown("""
- **교통 플로우 대체/보강**  
  - `utils.traffic_plot.plot_speed` ↔ `plot_nearby_speed_from_csv`(fallback)
  - 다른 공급자 데이터(예: API)로 대체 시 동일 스키마(`link_id,hour,평균속도`) 맞추기
- **혼잡 추정식 커스터마이징**  
  - 3-3 사분면의 `w(h)`/`η`/`r`(세대비) 조정, 새벽 스무딩(`apply_dawn_smoothing`) 파라미터 튜닝
- **재무 모델 확장**  
  - `numpy_financial` 활용해 IRR/NPV/캐시플로우 상세화, 토지비/이자/보조금 항목 추가
- **보고서 생성**  
  - `st.download_button`으로 CSV/PNG/Markdown 레포트 내보내기 탭 추가
- **다중 프로젝트 비교**  
  - 복수 단지 선택 후 교통·재무 결과를 그리드/스몰멀티플로 비교
""")

# ────────────────────────────────────────────────────────────────
# 8) 자주 묻는 질문(FAQ) / 트러블슈팅
# ────────────────────────────────────────────────────────────────
st.markdown("### 8) 트러블슈팅")
with st.expander("❗ 교통 CSV 또는 SHP가 없어 그래프/지도가 비어있어요"):
    st.markdown("""
- `data/`에 **AverageSpeed(LINK).xlsx**와 **seoul_link_lev5.5_2023.shp**(연관 파일 포함)을 넣어주세요.  
- 앱이 자동으로 XLSX→CSV(`AverageSpeed(LINK)_2023.csv`) 변환을 시도합니다.
- 파일명이 다르면 `app.py` 상단 경로 상수를 수정하세요.
""")
with st.expander("❗ 좌표가 없는 단지들이 있어요"):
    st.markdown("""
- `data/서울시_재개발재건축_clean_kakao.csv`에 `name, gu, lat, lon`을 보완하세요.
- 좌표가 없어도 임시로 **구 중심 + Jitter**로 지도에 표시되지만, 분석 정확도는 떨어집니다.
""")
with st.expander("❗ 메모리 사용량이 높아요 / 느려요"):
    st.markdown("""
- 반경/Top-N 슬라이더를 낮추고, 데이터셋을 연도/지역으로 분할하세요.
- `@st.cache_*`가 잘 적용되어 있는지 확인하고, 대형 변수의 세션 저장을 피하세요.
""")

# ────────────────────────────────────────────────────────────────
# 9) 실행/배포 팁
# ────────────────────────────────────────────────────────────────
st.markdown("### 9) 실행 & 배포")
st.code("""
# 로컬 실행
$ streamlit run app.py

# (선택) requirements.txt에 아래와 유사한 의존성 기입
streamlit
pandas
numpy
geopandas
pydeck
altair
numpy-financial
shapely
fiona
""".strip(), language="bash")

st.markdown("<br/>", unsafe_allow_html=True)
st.success("이 페이지는 운영/개발자 온보딩을 위한 문서 페이지입니다. 코드/경로가 바뀌면 **여기를 우선 업데이트** 해주세요.")
