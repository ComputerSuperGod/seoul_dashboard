# -------------------------------------------------------------
# 🏗 AIoT 스마트 인프라 대시보드 (재건축 의사결정 Helper)
# -------------------------------------------------------------
# 📊 CSV 기반 데이터 반영 버전
# -------------------------------------------------------------

# --- must come first: add project root to sys.path BEFORE importing utils ---
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # .../seoul_dashboard_3
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
# ---------------------------------------------------------------------------

import streamlit as st
import numpy_financial as npf
import json
import pandas as pd
import numpy as np
import pydeck as pdk
import altair as alt
import geopandas as gpd

from components.sidebar_presets import render_sidebar_presets
from components.sidebar_4quadrant_guide import render_sidebar_4quadrant_guide



from datetime import datetime

# === [SESSION KEYS INIT] ===
if "matched_links_geojson" not in st.session_state:
    st.session_state["matched_links_geojson"] = None
if "matched_links_geojson_daily" not in st.session_state:
    st.session_state["matched_links_geojson_daily"] = None
# [넣을 위치 A] color_mode 기본값
if "color_mode_daily_val" not in st.session_state:
    st.session_state["color_mode_daily_val"] = "절대(30/70)"

# === 외부 모듈 (utils) 임포트 ===
from utils.traffic_preproc import ensure_speed_csv

# Altair/MPL/Plotly 스위치형: plot_speed가 없거나 로딩 실패하면 기존 함수로 폴백
try:
    from utils.traffic_plot import plot_speed
    _HAS_PLOT_SPEED = True
except Exception as e:
    print("utils.traffic_plot import fallback:", e)
    from utils.traffic_plot import plot_nearby_speed_from_csv
    _HAS_PLOT_SPEED = False

# === 데이터 디렉터리 ===
DATA_DIR = BASE_DIR / "data"

# === 데이터 파일 경로 (이름 충돌 방지: 변수명 구분) ===
BASE_YEAR = 2023   # 24년으로 바꿔도 됨

# 재건축 프로젝트 원본 CSV (당신의 app에서 쓰던 표 데이터)
PROJECTS_CSV_PATH = DATA_DIR / "seoul_redev_projects.csv"

# 교통 기준년도 데이터 (엑셀 → CSV 자동 변환 대상)
TRAFFIC_XLSX_PATH = DATA_DIR / "AverageSpeed(LINK).xlsx"
TRAFFIC_CSV_PATH  = DATA_DIR / f"AverageSpeed_Seoul_{BASE_YEAR}.csv"

# 도로망 레벨55 쉐이프
SHP_PATH = DATA_DIR / "seoul_link_lev5.5_2023.shp"
LINK_ID_COL = "k_link_id"  # ✅ SHP의 링크 컬럼명

#===========================캐시 비우기=================
with st.sidebar:
    if st.button("캐시 비우기"):
        st.cache_data.clear()
        st.session_state["matched_links_geojson"] = None
        st.session_state["matched_links_geojson_daily"] = None
        st.rerun()
#======================================================

# 🔤 안전한 CSV 로더: 여러 인코딩 시도
def smart_read_csv(path, encodings=("utf-8-sig", "cp949", "euc-kr", "utf-8", "latin1")):
    import pandas as pd
    last_err = None
    for enc in encodings:
        try:
            df = pd.read_csv(path, encoding=enc)
            return df
        except UnicodeDecodeError as e:
            last_err = e
            continue
    # 최후 수단: errors='replace' 로라도 읽기
    try:
        df = pd.read_csv(path, encoding="utf-8", errors="replace")
        return df
    except Exception:
        raise last_err or Exception(f"Failed to read {path} with tried encodings.")

# -------------------------------------------------------------
# ✅ 프로젝트 루트 기준 경로 자동 설정
# -------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "data" / "seoul_redev_projects.csv"
CSV_ENCODING = "cp949"

# -------------------------------------------------------------
# 📦 좌표 CSV 병합 유틸
# -------------------------------------------------------------
COORD_CSV_PATH = BASE_DIR / "data" / "서울시_재개발재건축_clean_kakao.csv"
COORD_ENCODING = "utf-8-sig"  # (스마트 로더가 자동판별하므로 없어도 동작)

# 1) CSV 로드 유틸 (교통량 CSV)
@st.cache_data(show_spinner=False)
def load_volume_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["link_id"] = df["link_id"].astype(str)

    # 시간 안전 정규화: "0시", " 08 ", "8.0" 등도 0~23으로 변환
    h = pd.to_numeric(
        pd.Series(df["hour"]).astype(str).str.extract(r"(\d+)", expand=False),
        errors="coerce"
    ).fillna(0).astype(int) % 24
    df["hour"] = h

    df["차량대수"] = pd.to_numeric(df["차량대수"], errors="coerce").fillna(0)
    return df

# 2) 교통량 가중 혼잡빈도강도(CFI) 계산
def compute_cfi_weighted(speed_df: pd.DataFrame, vol_df: pd.DataFrame, boundary_speed: float = 30.0):
    d = speed_df.copy()
    d["link_id"] = d["link_id"].astype(str)
    d["hour"] = d["hour"].astype(int)
    d["평균속도(km/h)"] = pd.to_numeric(d["평균속도(km/h)"], errors="coerce")

    # merge
    m = d.merge(vol_df, on=["link_id", "hour"], how="inner")

    # 혼잡 차량수(속도<=경계값) vs 전체 차량수
    m["혼잡차량수"] = (m["평균속도(km/h)"] <= boundary_speed).astype(int) * m["차량대수"]
    g = m.groupby(["link_id", "hour"], as_index=False).agg(
        전체차량수=("차량대수", "sum"),
        혼잡차량수=("혼잡차량수", "sum"),
    )
    g["혼잡빈도강도(%)"] = (g["혼잡차량수"] / g["전체차량수"]).replace([float("inf"), float("nan")], 0) * 100
    return g

def compute_cfi_soft(
    speed_df: pd.DataFrame,
    vol_df: pd.DataFrame,
    boundary_mode: str = "percentile",  # "percentile" or "fixed"
    boundary_value: float = 40.0,       # percentile: 10~90(%), fixed: km/h
    tau_kmh: float = 6.0                # 시그모이드 급경사 폭(값이 크면 더 부드러움)
):
    """
    평균속도(시간대별 1개) + 시간대 총 차량대수만 있을 때
    시그모이드 기반의 '부드러운' 혼잡 확률을 만들어 교통량 가중 CFI 근사.
    """
    # --- 속도 데이터 정리 ---
    d = speed_df.copy()
    d["link_id"] = d["link_id"].astype(str)
    d["hour"] = pd.to_numeric(d["hour"], errors="coerce").astype("Int64")  # allow NA
    d["평균속도(km/h)"] = pd.to_numeric(d["평균속도(km/h)"], errors="coerce")

    # --- 교통량 데이터 정리 ---
    v = vol_df.copy()
    v["link_id"] = v["link_id"].astype(str)
    v["hour"] = pd.to_numeric(v["hour"], errors="coerce").astype("Int64") % 24
    v["차량대수"] = pd.to_numeric(v["차량대수"], errors="coerce").fillna(0)

    # --- 병합 ---
    m = d.merge(v, on=["link_id", "hour"], how="inner").dropna(subset=["평균속도(km/h)"])
    if m.empty:
        out = m[["link_id","hour"]].copy()
        out["혼잡빈도강도(%)"] = 0.0
        out.attrs = {"boundary": np.nan, "mode": boundary_mode}
        return out

    # --- 경계속도 결정 ---
    if boundary_mode == "percentile":
        p = float(boundary_value)
        p = max(5.0, min(95.0, p))  # 안전 범위
        vb = float(np.nanpercentile(m["평균속도(km/h)"], p))
    else:
        vb = float(boundary_value)

    # --- 시그모이드 혼잡확률 ---
    tau = max(1e-6, float(tau_kmh))
    m["p_cong"] = 1.0 / (1.0 + np.exp((m["평균속도(km/h)"] - vb) / tau))

    # --- 링크×시간대로 집계 (교통량 가중 평균) ---
    def _wavg(x, w):
        w = np.asarray(w)
        x = np.asarray(x)
        mask = np.isfinite(x) & np.isfinite(w) & (w >= 0)
        if not mask.any():
            return 0.0
        return float((x[mask] * w[mask]).sum() / max(1e-9, w[mask].sum()))

    g = (
        m.groupby(["link_id","hour"], as_index=False)
         .apply(lambda df: pd.Series({
             "혼잡빈도강도(%)": _wavg(df["p_cong"], df["차량대수"]) * 100.0
         }))
         .reset_index()
    )

    # 안전 클립
    g["혼잡빈도강도(%)"] = g["혼잡빈도강도(%)"].clip(0, 100)
    g.attrs = {"boundary": vb, "mode": boundary_mode, "tau": tau}
    return g
# === 색상 스케일: 절대/상대 선택 ===
def color_by_value(v: float):
    if pd.isna(v): return (200,200,200)
    v = float(v)
    if v < 30:   return (0, 200, 0)       # 초록
    if v < 70:   return (255, 200, 0)     # 노랑
    return (255, 0, 0)                    # 빨강

def color_by_quantile(v: float, q30: float, q70: float):
    if pd.isna(v): return (200,200,200)
    if v < q30:   return (0, 200, 0)
    if v < q70:   return (255, 200, 0)
    return (255, 0, 0)



@st.cache_data(show_spinner=False)
def load_coords() -> pd.DataFrame:
    df = smart_read_csv(COORD_CSV_PATH)

    # 숫자화
    df["lat"] = pd.to_numeric(df.get("lat"), errors="coerce")
    df["lon"] = pd.to_numeric(df.get("lon"), errors="coerce")

    # 안전한 병합용 기초 컬럼 생성
    def coalesce(a, b):
        a = "" if a is None else str(a).strip()
        b = "" if b is None else str(b).strip()
        return a if a else b

    # name, address 만들기
    if ("정비구역명칭" in df.columns) or ("추진위원회/조합명" in df.columns):
        name = [coalesce(n, m) for n, m in zip(df.get("정비구역명칭"), df.get("추진위원회/조합명"))]
    else:
        name = df.get("name")

    address = [coalesce(a, b) for a, b in zip(df.get("정비구역위치"), df.get("대표지번"))]

    out = pd.DataFrame({
        "apt_id": df.get("사업번호").astype(str) if "사업번호" in df.columns else "",
        "name": pd.Series(name, index=df.index),
        "gu": df.get("자치구"),
        "address": pd.Series(address, index=df.index),
        "full_address": df.get("full_address"),
        "lat": df["lat"],
        "lon": df["lon"],
    })
    for col in ["apt_id", "name", "gu", "address", "full_address"]:
        if col in out.columns:
            out[col] = out[col].fillna("").astype(str).str.strip()
    return out

@st.cache_data(show_spinner=False)
def merge_projects_with_coords(gu: str) -> pd.DataFrame:
    # 1) 원본 로드 + 스키마 통일
    raw = load_raw_csv()
    proj = normalize_schema(raw)
    proj = proj[proj["gu"] == gu].copy()

    # 2) 좌표 로드
    coords = load_coords()
    coords = coords[coords["gu"] == gu].copy()

    # 3) ✅ name+gu 기준으로 매칭하고 full_address까지 가져오기
    out = proj.merge(
        coords[["name", "gu", "lat", "lon", "full_address"]],
        on=["name", "gu"],
        how="left"
    )

    # 4) 좌표 결측 보정 (구 중심 + 지터)
    missing = out["lat"].isna() | out["lon"].isna()
    base_lat, base_lon = GU_CENTER.get(gu, (37.55, 127.0))
    rng = np.random.default_rng(42)
    jitter = lambda n: rng.normal(0, 0.002, n)  # ≈ 200m
    if missing.any():
        n = int(missing.sum())
        out.loc[missing, "lat"] = base_lat + jitter(n)
        out.loc[missing, "lon"] = base_lon + jitter(n)
    out["has_geo"] = ~missing

    # 5) ✅ 표시용 주소: full_address 우선, 없으면 원본 address
    out["address_display"] = out["full_address"].fillna("").replace("", pd.NA)
    out["address_display"] = out["address_display"].fillna(out["address"]).fillna("")

    return out.reset_index(drop=True)

# -------------------------------------------------------------
# ⚙️ Streamlit 기본 설정
# -------------------------------------------------------------
st.set_page_config(
    page_title="AIoT 스마트 인프라 대시보드 | 재건축 Helper",
    layout="wide",
)

st.markdown("""
<style>
/* 모든 LaTeX 수식을 왼쪽 정렬로 */
.katex-display {
    text-align: left !important;
    margin-left: 0 !important;
}

/* 텍스트 전체 기본 왼쪽 정렬 유지 */
.block-container {
    text-align: left !important;
}
</style>
""", unsafe_allow_html=True)

STYLE = """
<style>
.small-muted { color: #7a7a7a; font-size: 0.9rem; }
.kpi-card { padding: 16px; border-radius: 16px; background: #111827; border: 1px solid #1f2937; }
.kpi-title { font-size: 0.9rem; color: #9ca3af; margin-bottom: 8px; }
.kpi-value { font-size: 1.4rem; font-weight: 700; color: #e5e7eb; }
.section-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 8px; }
hr.soft { border: none; height: 1px; background: #1f2937; margin: 16px 0; }
</style>
"""
st.markdown(STYLE, unsafe_allow_html=True)

st.markdown("""
<style>
div[data-testid="stMarkdownContainer"] .katex-display {
    text-align: left !important;
    margin-left: 0 !important;
    margin-right: auto !important;
}
div[data-testid="stMarkdownContainer"] .katex-display > .katex {
    display: inline-block !important;
}
div[data-testid="stMarkdownContainer"] p {
    text-align: left !important;
    margin-left: 0 !important;
}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 🧾 CSV 로드 & 전처리
# -------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_raw_csv() -> pd.DataFrame:
    return smart_read_csv(PROJECTS_CSV_PATH)  # ✅ 인코딩 자동 감지 사용

def _coalesce(*vals):
    for v in vals:
        if pd.notna(v) and str(v).strip():
            return v
    return None

def normalize_schema(df_raw: pd.DataFrame) -> pd.DataFrame:
    c = df_raw.columns
    get = lambda name: df_raw[name] if name in c else pd.Series([None]*len(df_raw))

    def _num(x):
        return pd.to_numeric(pd.Series(x, index=df_raw.index), errors="coerce")

    def _pct_to_num(x):
        s = pd.Series(x, index=df_raw.index).astype(str).str.replace("%", "", regex=False)
        s = s.str.replace(",", "", regex=False)
        return pd.to_numeric(s, errors="coerce")

    def _floors_to_num(x):
        s = pd.Series(x, index=df_raw.index).astype(str).str.extract(r"(-?\d+)", expand=False)
        return pd.to_numeric(s, errors="coerce")

    # 기본 스키마 매핑
    df = pd.DataFrame({
        "apt_id": get("사업번호"),
        "name": [v if (pd.notna(v) and str(v).strip()) else w for v, w in zip(get("정비구역명칭"), get("추진위원회/조합명"))],
        "org_name": get("추진위원회/조합명"),
        "biz_type": get("사업구분"),
        "op_type": get("운영구분"),
        "gu": get("자치구"),
        "address": [v if (pd.notna(v) and str(v).strip()) else w for v, w in zip(get("정비구역위치"), get("대표지번"))],
        "households": _num(get("분양세대총수")),
        "land_area_m2": _num(get("정비구역면적(㎡)")),
        "far": _pct_to_num(get("용적률")),
        "floors": _floors_to_num(get("층수")),
        "status": get("진행단계"),
        "floors_up": _floors_to_num(get("지상층수")),
        "floors_down": _floors_to_num(get("지하층수")),
    })

    def _fmt_floor(u, d):
        parts = []
        if pd.notna(u):
            parts.append(f"지상 {int(u)}")
        if pd.notna(d):
            parts.append(f"지하 {int(d)}")
        return " / ".join(parts)

    df["floors_display"] = [_fmt_floor(u, d) for u, d in zip(df["floors_up"], df["floors_down"])]
    df["floors_show"] = df["floors_display"].fillna("").astype(str).str.strip()
    mask_empty = df["floors_show"] == ""
    df.loc[mask_empty, "floors_show"] = df.loc[mask_empty, "floors"].apply(
        lambda x: f"{int(x)}층" if pd.notna(x) else ""
    )

    df["apt_id"] = df["apt_id"].astype(str)
    df["name"] = df["name"].fillna("무명 정비구역")
    for col in ["org_name","biz_type","op_type","gu","address","status"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    return df

@st.cache_data(show_spinner=False)
def get_projects_by_gu(gu: str) -> pd.DataFrame:
    raw = load_raw_csv()
    norm = normalize_schema(raw)
    return norm[norm["gu"] == gu].reset_index(drop=True)

# -------------------------------------------------------------
# 📍 서울시 25개 자치구 리스트 & 중심좌표
# -------------------------------------------------------------
DISTRICTS = [
    "강남구","강동구","강북구","강서구","관악구","광진구","구로구","금천구",
    "노원구","도봉구","동대문구","동작구","마포구","서대문구","서초구","성동구",
    "성북구","송파구","양천구","영등포구","용산구","은평구","종로구","중구","중랑구"
]

GU_CENTER = {
    "강남구": (37.5172, 127.0473),
    "강동구": (37.5301, 127.1238),
    "강북구": (37.6396, 127.0257),
    "강서구": (37.5509, 126.8495),
    "관악구": (37.4784, 126.9516),
    "광진구": (37.5386, 127.0822),
    "구로구": (37.4955, 126.8876),
    "금천구": (37.4569, 126.8958),
    "노원구": (37.6543, 127.0565),
    "도봉구": (37.6688, 127.0471),
    "동대문구": (37.5740, 127.0396),
    "동작구": (37.5124, 126.9393),
    "마포구": (37.5638, 126.9084),
    "서대문구": (37.5791, 126.9368),
    "서초구": (37.4836, 127.0326),
    "성동구": (37.5633, 127.0369),
    "성북구": (37.5894, 127.0167),
    "송파구": (37.5145, 127.1068),
    "양천구": (37.5169, 126.8665),
    "영등포구": (37.5264, 126.8963),
    "용산구": (37.5311, 126.9811),
    "은평구": (37.6176, 126.9227),
    "종로구": (37.5736, 126.9780),
    "중구": (37.5636, 126.9976),
    "중랑구": (37.6063, 127.0929),
}

def attach_latlon_by_gu_centroid(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["lat"] = df["gu"].map(lambda g: GU_CENTER.get(g, (37.55, 127.0))[0]) + np.random.normal(scale=0.004, size=len(df))
    df["lon"] = df["gu"].map(lambda g: GU_CENTER.get(g, (37.55, 127.0))[1]) + np.random.normal(scale=0.004, size=len(df))
    return df

# -------------------------------------------------------------
# 🧭 사이드바
# -------------------------------------------------------------
st.sidebar.title("재건축 의사결정 Helper")

# 사이드바 - 구 선택
selected_gu = st.sidebar.selectbox("구 선택", DISTRICTS, index=0)

# ✅ 세션에 선택 인덱스 초기화(맨 위 한 번)
if "selected_row" not in st.session_state:
    st.session_state.selected_row = None
if "selected_gu_prev" not in st.session_state:
    st.session_state.selected_gu_prev = selected_gu

if st.session_state.selected_gu_prev != selected_gu:
    st.session_state.selected_row = None
    st.session_state.selected_gu_prev = selected_gu

st.sidebar.markdown(
    "<div class='small-muted'>구 선택 시, 해당 구의 정비사업 단지 목록과 지도가 갱신됩니다.</div>",
    unsafe_allow_html=True,
)

project_name = st.sidebar.text_input("프로젝트 이름", value=f"{selected_gu} 재건축 시나리오")

# 사이드바 FAQ 렌더
render_sidebar_presets()
render_sidebar_4quadrant_guide()

# -------------------------------------------------------------
# 🗺️ 1-2사분면: 지도 + 단지 선택
# -------------------------------------------------------------
col12_left, col12_right = st.columns([2.2, 1.4], gap="large")

with col12_left:
    st.markdown("### 🗺 [1-2사분면] · 지도 & 단지선택")

    base_df = get_projects_by_gu(selected_gu)
    df_map = merge_projects_with_coords(selected_gu)

    # 지도 자리만 먼저 확보 (필터/선택 적용 후 아래에서 실제 차트 렌더)
    map_slot = st.empty()

    if df_map.empty:
        st.warning("⚠️ 해당 구에 데이터가 없습니다.")
        st.stop()

# ---------------------------
# 📋 단지 테이블 + 필터 UI
# ---------------------------
with st.expander("🔍 데이터 소스 확인(임시)", expanded=False):
    raw = load_raw_csv()
    cols_raw = ["자치구", "정비구역명칭", "추진위원회/조합명", "분양세대총수", "정비구역면적(㎡)"]
    exist_cols = [c for c in cols_raw if c in raw.columns]
    st.caption(f"원본: {CSV_PATH.name} · 표시열: {', '.join(exist_cols)}")
    try:
        st.dataframe(
            raw[exist_cols][raw["자치구"] == selected_gu].head(20),
            use_container_width=True
        )
    except Exception:
        st.dataframe(raw[exist_cols].head(20), use_container_width=True)

    st.caption("현재 표시값(df_map)")
    st.dataframe(
        df_map[["gu", "address_display", "name", "households", "land_area_m2"]].head(20),
        use_container_width=True
    )

    def _coalesce(a, b):
        a = "" if a is None else str(a).strip()
        b = "" if b is None else str(b).strip()
        return a if a else b

    raw_norm = pd.DataFrame({
        "gu": raw.get("자치구"),
        "name_raw": [
            _coalesce(n, m) for n, m in zip(
                raw.get("정비구역명칭"),
                raw.get("추진위원회/조합명")
            )
        ],
        "households_src": pd.to_numeric(raw.get("분양세대총수"), errors="coerce"),
        "land_area_m2_src": pd.to_numeric(raw.get("정비구역면적(㎡)"), errors="coerce"),
    })

    comp = df_map.merge(
        raw_norm, left_on=["name","gu"], right_on=["name_raw","gu"], how="left"
    )

    hh_match  = (comp["households"].fillna(-1).astype(float) == comp["households_src"].fillna(-1).astype(float))
    area_match = np.isclose(
        comp["land_area_m2"].astype(float),
        comp["land_area_m2_src"].astype(float),
        rtol=1e-6, atol=1e-6, equal_nan=True
    )

    comp["households_match"] = hh_match
    comp["land_area_match"]  = area_match

    total = len(comp)
    hh_ok  = int(hh_match.sum())
    ar_ok  = int(area_match.sum())

    st.write(
        f"✅ 세대수 일치: **{hh_ok}/{total}**  ·  "
        f"✅ 면적 일치: **{ar_ok}/{total}**"
    )

    bad = comp[~(hh_match & area_match)][
        ["gu","address_display","name","households","households_src","land_area_m2","land_area_m2_src"]
    ]
    if not bad.empty:
        st.warning("불일치 샘플(최대 20건):")
        st.dataframe(bad.head(20), use_container_width=True)

st.markdown("**단지 목록**")

df_list = df_map[[
    "apt_id",
    "address_display",
    "org_name", "biz_type", "op_type",
    "status",
    "households", "land_area_m2",
    "far",
    "floors_show",
]].copy()

df_list["households"]   = pd.to_numeric(df_list["households"], errors="coerce")
df_list["land_area_m2"] = pd.to_numeric(df_list["land_area_m2"], errors="coerce")
df_list["far"]          = pd.to_numeric(df_list["far"], errors="coerce")

# ===== 필터 영역 =====
fcol1, fcol2, fcol3, fcol4 = st.columns([1.6, 1.4, 1.6, 1.2])
with fcol1:
    kw = st.text_input("검색어(주소/조합명/키워드)", value="", placeholder="예) 개포, 목동, 조합")

HH_BUCKETS = {
    "전체": (None, None),
    "~ 300세대": (0, 300),
    "301–500세대": (301, 500),
    "501–1,000세대": (501, 1000),
    "1,001–2,000세대": (1001, 2000),
    "2,001세대 이상": (2001, None),
}

AREA_BUCKETS = {
    "전체": (None, None),
    "~ 30,000 m²": (0, 30000),
    "30,001–50,000 m²": (30001, 50000),
    "50,001–100,000 m²": (50001, 100000),
    "100,001–200,000 m²": (100001, 200000),
    "200,001 m² 이상": (200001, None),
}

with fcol2:
    hh_choice = st.selectbox("세대수 범주", list(HH_BUCKETS.keys()), index=0)
with fcol3:
    la_choice = st.selectbox("면적 범주(m²)", list(AREA_BUCKETS.keys()), index=0)
with fcol4:
    hide_zero = st.checkbox("0/결측치 숨기기", value=True)

mask = pd.Series(True, index=df_list.index)

if kw.strip():
    _kw = kw.strip().lower()
    mask &= (
        df_list["address_display"].fillna("").str.lower().str.contains(_kw) |
        df_list["org_name"].fillna("").str.lower().str.contains(_kw)
    )

hh_lo, hh_hi = HH_BUCKETS[hh_choice]
la_lo, la_hi = AREA_BUCKETS[la_choice]

col_series = df_list["households"].fillna(-1)
if hh_lo is not None:
    mask &= col_series >= hh_lo
if hh_hi is not None:
    mask &= col_series <= hh_hi

col_series = df_list["land_area_m2"].fillna(-1)
if la_lo is not None:
    mask &= col_series >= la_lo
if la_hi is not None:
    mask &= col_series <= la_hi

if hide_zero:
    mask &= df_list["households"].fillna(0) > 0
    mask &= df_list["land_area_m2"].fillna(0) > 0

filtered = df_list[mask].reset_index().rename(columns={"index": "orig_index"})

scol1, scol2 = st.columns([1.2, 1.2])
with scol1:
    sort_key = st.selectbox("정렬 기준",
        ["세대수 내림차순", "세대수 오름차순", "면적 내림차순", "면적 오름차순", "주소 오름차순"], index=0)
with scol2:
    topn = st.selectbox("표시 개수", [10, 20, 50, 100, "전체"], index=1)

if sort_key == "세대수 내림차순":
    filtered = filtered.sort_values("households", ascending=False, na_position="last")
elif sort_key == "세대수 오름차순":
    filtered = filtered.sort_values("households", ascending=True, na_position="last")
elif sort_key == "면적 내림차순":
    filtered = filtered.sort_values("land_area_m2", ascending=False, na_position="last")
elif sort_key == "면적 오름차순":
    filtered = filtered.sort_values("land_area_m2", ascending=True, na_position="last")
elif sort_key == "주소 오름차순":
    filtered = filtered.sort_values("address_display", ascending=True, na_position="last")

if topn != "전체":
    filtered = filtered.head(int(topn))

show_df = filtered[[
    "orig_index",
    "address_display", "org_name", "biz_type", "op_type",
    "status",
    "households", "land_area_m2",
    "far", "floors_show",
]].copy().rename(columns={
    "address_display": "주소",
    "org_name": "추진위원회/조합명",
    "biz_type": "사업구분",
    "op_type": "운영구분",
    "status": "진행단계",
    "households": "계획세대수",
    "land_area_m2": "면적",
    "far": "용적률(%)",
    "floors_show": "층수",
})

show_df.insert(1, "선택", False)

curr_ids = show_df["orig_index"].tolist()
if (st.session_state.selected_row is None) or (st.session_state.selected_row not in curr_ids):
    st.session_state.selected_row = int(curr_ids[0]) if curr_ids else None
show_df.loc[show_df["orig_index"] == st.session_state.selected_row, "선택"] = True

edited = st.data_editor(
    show_df,
    use_container_width=True,
    hide_index=True,
    disabled=[
        "orig_index", "주소", "추진위원회/조합명", "사업구분", "운영구분",
        "진행단계", "계획세대수", "면적", "용적률(%)", "층수"
    ],
    column_config={
        "orig_index": st.column_config.NumberColumn("원본인덱스", help="내부 선택용", width="small"),
        "선택": st.column_config.CheckboxColumn("선택", help="이 행을 선택"),
        "주소": st.column_config.TextColumn("주소"),
        "추진위원회/조합명": st.column_config.TextColumn("추진위원회/조합명"),
        "사업구분": st.column_config.TextColumn("사업구분"),
        "운영구분": st.column_config.TextColumn("운영구분"),
        "진행단계": st.column_config.TextColumn("진행단계"),
        "계획세대수": st.column_config.NumberColumn("계획세대수", format="%,d"),
        "면적": st.column_config.NumberColumn("면적(m²)", format="%,d"),
        "용적률(%)": st.column_config.NumberColumn("용적률(%)", format=",.1f"),
        "층수": st.column_config.TextColumn("층수"),
    },
    key=f"project_table_{selected_gu}",
)

prev = st.session_state.selected_row
sel_list = [int(x) for x in edited.loc[edited["선택"] == True, "orig_index"].tolist()]

if len(sel_list) == 0:
    if prev in curr_ids:
        st.session_state.selected_row = int(prev)
    elif curr_ids:
        st.session_state.selected_row = int(curr_ids[0])
elif len(sel_list) == 1:
    st.session_state.selected_row = int(sel_list[0])
else:
    if prev in sel_list:
        new_choice = next((x for x in sel_list if x != prev), sel_list[0])
    else:
        new_choice = sel_list[0]
    st.session_state.selected_row = int(new_choice)
    st.rerun()

if st.session_state.selected_row is None:
    st.info("선택된 행이 없습니다.")
    st.stop()
selected_row = st.session_state.selected_row


# ✅ 4사분면 연동용 세션 설정
selected_site_name = df_map.loc[selected_row, "name"]
st.session_state["selected_site"] = selected_site_name


# ✅ 지도 데이터/레이어 만들기 (selected_row 확정 이후)
filtered_indices = edited["orig_index"].tolist()
map_data = df_map.loc[filtered_indices].reset_index(drop=True)

# ⬇︎ 추가
def _point_tooltip(row):
    addr = row.get("address_display", "")
    gu = row.get("gu", "")
    hh = row.get("households", "")
    la = row.get("land_area_m2", "")
    return (f"<b>{addr}</b><br/>"
            f"자치구: {gu}<br/>"
            f"세대수: {hh}<br/>"
            f"구역면적(m²): {la}")

map_data = map_data.copy()
map_data["tooltip_html"] = map_data.apply(_point_tooltip, axis=1)

highlight_row = df_map.loc[[selected_row]].assign(_selected=True)
highlight_row = highlight_row.copy()
highlight_row["tooltip_html"] = highlight_row.apply(_point_tooltip, axis=1)


sel_lat = float(df_map.loc[selected_row, "lat"])
sel_lon = float(df_map.loc[selected_row, "lon"])
view_state = pdk.ViewState(latitude=sel_lat, longitude=sel_lon, zoom=12.5)

layer_points = pdk.Layer(
    "ScatterplotLayer",
    data=map_data,
    get_position='[lon, lat]',
    get_radius=60,
    pickable=True,
    get_fill_color=[255, 140, 0, 160],
    get_line_color=[255, 255, 255],
    line_width_min_pixels=0.5,
)

highlight_row = df_map.loc[[selected_row]].assign(_selected=True)
layer_highlight = pdk.Layer(
    "ScatterplotLayer",
    data=highlight_row,
    get_position='[lon, lat]',
    get_radius=150,
    pickable=False,
    get_fill_color=[0, 200, 255, 220],
    get_line_color=[0, 0, 0],
    line_width_min_pixels=1.2,
)

tooltip = {
    "html": "{tooltip_html}",
    "style": {"backgroundColor": "#0f172a", "color": "white"},
}


with col12_right:
    st.markdown("### 🧾 [1사분면] · 기존 단지 정보")
    current = df_map.loc[selected_row]
    with st.container(border=True):
        st.markdown("**기존 단지 정보**")
        st.markdown(
            f"- 주소: **{current['address_display']}**\n\n"
            f"- 추진위원회/조합명: **{current['org_name']}**\n\n"
            f"- 자치구: **{current['gu']}**\n\n"
            f"- 계획 세대수: **{int(current['households']) if pd.notna(current['households']) else '미상'} 세대**\n\n"
            f"- 정비구역면적: **{int(current['land_area_m2']):,} m²**"
        )

    # ✅ 여기 두 줄 추가: (1) 라디오 놓을 자리 (2) 범례 자리
    color_controls_slot = st.container()
    legend_slot = st.empty()



# 3–4사분면 레이아웃 컬럼
# ✅ 아래 왼쪽(3사분면)=col4, 아래 오른쪽(4사분면)=col3
col4, col3 = st.columns([1.6, 1.4], gap="large")

# === 4-1사분면: 혼잡도 그래프 ===
with st.spinner("교통 기준년도 데이터 준비 중..."):
    if TRAFFIC_XLSX_PATH.exists():
        ensure_speed_csv(TRAFFIC_XLSX_PATH, TRAFFIC_CSV_PATH)
    elif not TRAFFIC_CSV_PATH.exists():
        st.warning(f"기준 CSV가 없습니다: {TRAFFIC_CSV_PATH.name}\n"
                   f"→ data 폴더에 {TRAFFIC_XLSX_PATH.name} 를 넣으면 자동 변환됩니다.")

sel_lat = float(current.get("lat", 37.5667))
sel_lon = float(current.get("lon", 126.9784))

def _to_norm_str_id(s):
    return (
        pd.Series(s, dtype="object")
          .astype(str)
          .str.replace(r"\.0$", "", regex=True)
          .str.strip()
    )

with col3:
    st.markdown("### 🚦 [4-1사분면] · 주변 도로 혼잡도 (기준년도)")

    radius = st.slider("반경(m)", 500, 3000, 1000, step=250, key="radius_m")
    graph_topn = st.slider("그래프에 표시할 링크 수 (Top-N)", 5, 50, 10, 1, key="graph_topn")

    df_plot_all = None

    # ✅ A) 그래프용 — 평균속도 Top-N만 표시
    if TRAFFIC_CSV_PATH.exists() and SHP_PATH.exists():
        if _HAS_PLOT_SPEED:
            chart_speed, df_speed = plot_speed(
                csv_path=TRAFFIC_CSV_PATH,
                shp_path=SHP_PATH,
                center_lon=sel_lon,
                center_lat=sel_lat,
                radius_m=radius,
                max_links=graph_topn,  # 그래프: Top-N만
                renderer="altair",
                chart_height=280,
            )
            st.altair_chart(chart_speed, use_container_width=True, theme=None)

            # ✅ B) 지도용 — 반경 내 모든 링크 (혼잡도 계산용)
            _, df_plot_all = plot_speed(
                csv_path=TRAFFIC_CSV_PATH,
                shp_path=SHP_PATH,
                center_lon=sel_lon,
                center_lat=sel_lat,
                radius_m=radius,
                max_links=10000,  # 지도: 반경 내 전부
                renderer="altair",
                chart_height=1,  # 더미 (표시 안 함)
            )
        else:
            # fallback (plot_speed 불가 시)
            _fig_ignored, df_plot_all = plot_nearby_speed_from_csv(
                csv_path=TRAFFIC_CSV_PATH,
                shp_path=SHP_PATH,
                center_lon=sel_lon,
                center_lat=sel_lat,
                radius_m=radius,
                max_links=10000,
            )
    else:
        st.info("교통 CSV 또는 SHP가 없어 그래프/지도 데이터를 만들 수 없습니다.")

    # === 혼잡도 계산 ===
    if (df_plot_all is not None) and (not df_plot_all.empty):
        st.markdown("### 📈 [4-2사분면] 혼잡지표 (혼잡도)")

        # 혼잡도 계산
        def compute_congestion_from_speed(df_plot):
            d = df_plot.copy()
            d["평균속도(km/h)"] = pd.to_numeric(d["평균속도(km/h)"], errors="coerce")
            d["free_flow"] = d.groupby("link_id")["평균속도(km/h)"].transform("max").clip(lower=1)
            d["혼잡도(%)"] = ((1 - (d["평균속도(km/h)"] / d["free_flow"]).clip(0, 1)) * 100).clip(0, 100)
            return d.rename(columns={"혼잡도(%)": "value"})[["link_id", "hour", "value"]]

        df_metric_all = compute_congestion_from_speed(df_plot_all)
        y_title = "혼잡도 (0=자유주행, 100=매우혼잡)"

        # 일평균 계산
        df_daily = (
            df_metric_all.groupby("link_id", as_index=False)["value"].mean()
            .rename(columns={"value": "daily_value"})
        )
        df_daily["link_id_norm"] = (
            pd.Series(df_daily["link_id"], dtype="object")
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.strip()
        )

        gdf_link = gpd.read_file(SHP_PATH)[[LINK_ID_COL, "geometry"]]
        if gdf_link.crs and gdf_link.crs.to_epsg() != 4326:
            gdf_link = gdf_link.to_crs(epsg=4326)
        gdf_link["link_id_norm"] = (
            gdf_link[LINK_ID_COL].astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.strip()
        )

        gdf_vis = gdf_link.merge(df_daily, on="link_id_norm", how="inner")

        # === 지도 색 기준 (단 1개만 사용, 키 고유화) ===
        # ✅ (교체) — 라디오를 1사분면 아래의 slot에 렌더
        with color_controls_slot:
            color_mode_key = f"color_mode_daily__{selected_gu}"
            st.radio(
                "지도 색 기준",
                ["절대(30/70)", "상대(30%/70%)"],
                index=0,
                horizontal=True,
                key=color_mode_key,
            )
            st.caption("절대: 30/70 고정 · 상대: 반경 내 분포의 30/70 분위수")

        # 선택값 세션에서 꺼내 쓰기
        color_mode = st.session_state.get(color_mode_key, "절대(30/70)")
        st.session_state["color_mode_daily_val"] = color_mode

        # 색상 계산 분기 (그대로 사용)
        if not gdf_vis.empty:
            if color_mode.startswith("상대"):
                q30 = float(np.nanpercentile(gdf_vis["daily_value"], 30))
                q70 = float(np.nanpercentile(gdf_vis["daily_value"], 70))
                cols = list(zip(*gdf_vis["daily_value"].apply(lambda x: color_by_quantile(x, q30, q70))))
            else:
                cols = list(zip(*gdf_vis["daily_value"].apply(color_by_value)))
            gdf_vis["color_r"], gdf_vis["color_g"], gdf_vis["color_b"] = cols[0], cols[1], cols[2]
            gdf_vis["tooltip_html"] = (
                    "<b>링크:</b> " + gdf_vis["link_id_norm"].astype(str)
                    + "<br/><b>일평균 혼잡도:</b> " + gdf_vis["daily_value"].round(1).astype(str) + "%"
            )
            st.session_state["matched_links_geojson_daily"] = json.loads(gdf_vis.to_json())
        else:
            st.session_state["matched_links_geojson_daily"] = None

        # ✅ 범례도 1사분면 아래의 legend_slot에 출력
        if st.session_state.get("matched_links_geojson_daily"):
            cmode = st.session_state.get("color_mode_daily_val", "절대(30/70)")
            legend_text = "🟩 <30% 분위 · 🟨 30~70% · 🟥 ≥70%" if cmode.startswith("상대") \
                else "🟩 <30 · 🟨 30~70 · 🟥 ≥70 (단위: %)"
            legend_slot.caption(legend_text)



        # === 그래프: Top-N 링크만 ===
        rank = (
            df_metric_all.groupby("link_id", as_index=False)["value"].mean()
            .sort_values("value", ascending=False)
            .head(graph_topn)
        )
        keep = set(rank["link_id"].astype(str))
        df_metric_chart = df_metric_all[df_metric_all["link_id"].astype(str).isin(keep)].copy()

        chart = (
            alt.Chart(df_metric_chart)
            .mark_line(point=True)
            .encode(
                x=alt.X("hour:Q", title="시간대 (시)"),
                y=alt.Y("value:Q", title=y_title, scale=alt.Scale(domain=[0, 100])),
                color=alt.Color("link_id:N", title="링크 ID",
                                legend=alt.Legend(orient="bottom", direction="horizontal", columns=4)),
                tooltip=[
                    alt.Tooltip("link_id:N", title="링크"),
                    alt.Tooltip("hour:Q", title="시"),
                    alt.Tooltip("value:Q", title=y_title, format=".1f"),
                ],
            )
            .properties(title=f"혼잡도 변화 추이 — Top {graph_topn}", width=1000, height=400)
            .configure_view(strokeWidth=0)
        )
        st.altair_chart(chart, use_container_width=False, theme=None)

        # === 정의 설명 ===
        st.markdown("### 🧮 혼잡도(%) 정의")
        st.markdown("- 링크 $(l)$, 시간대 $(h)$에서의 평균속도를 $v_{l,h}$ 라 할 때,")
        st.latex(r"v_{\mathrm{ff},l}=\max v_{l,h}")
        st.latex(r"\mathrm{혼잡도}_{l,h}(\%)=\Big(1-\min\big(1,\frac{v_{l,h}}{v_{\mathrm{ff},l}}\big)\Big)\times 100")
        st.markdown("- 값의 의미: **0% = 자유주행**, **100% = 매우 혼잡**")
    else:
        st.info("혼잡도 데이터를 계산할 수 없습니다.")


# ================================================================
# 🗺️ 1–2사분면 단일 렌더 블록 (daily → hourly → points/highlight)
# ================================================================
with col12_left:
    layers = []
    # 1) 일평균 혼잡도 GeoJSON 우선
    gj_daily = st.session_state.get("matched_links_geojson_daily")
    if gj_daily:
        layer_links = pdk.Layer(
            "GeoJsonLayer",
            data=gj_daily,
            pickable=True,
            auto_highlight=True,
            get_line_color='[properties.color_r, properties.color_g, properties.color_b, 220]',
            lineWidthMinPixels=3,
        )
        layers.append(layer_links)
    else:
        # 2) 없으면 시간대 기준 GeoJSON
        gj_hourly = st.session_state.get("matched_links_geojson")
        if gj_hourly:
            layer_links = pdk.Layer(
                "GeoJsonLayer",
                data=gj_hourly,
                pickable=True,
                auto_highlight=True,
                get_line_color=[255, 80, 80, 220],
                lineWidthMinPixels=3,
            )
            layers.append(layer_links)

    # 3) 기본 점/하이라이트는 항상 추가
    layers += [layer_points, layer_highlight]

    map_slot.pydeck_chart(
        pdk.Deck(
            layers=layers,
            initial_view_state=view_state,
            tooltip=tooltip,
        )
    )





# -------------------------------------------------------------
# 💡 3사분면 · 시나리오/재무/민감도/리포트 (업그레이드 버전)
# -------------------------------------------------------------
with col4:
    st.markdown("### 🧾 [3사분면] · 시나리오 & 재무/민감도 & 리포트")

    # ---------------------------
    # 0) 공통 유틸
    # ---------------------------
    def calc_kpis(
        households:int,
        avg_py:float,                 # 전용평형(평)
        sale_price_per_m2:float,      # 분양가 (만원/㎡)
        build_cost_per_m2:float,      # 공사비 (만원/㎡)
        infra_invest_billion:float,   # 교통 등 인프라 투자(억원)
        congestion_base:float,        # 기준 혼잡도(%)
        bus_inc_pct:int,              # 버스 증편(%)
        non_sale_ratio:float=0.15,    # 비분양 비율(공공/커뮤니티 등)
        sale_rate:float=0.98,         # 분양률
        disc_rate:float=0.07,         # 할인율
        years:int=4                   # 회수기간(년)
    ):
        # 면적 환산
        m2_per_py = 3.3058
        avg_m2 = avg_py * m2_per_py
        sellable_m2 = households * avg_m2 * (1 - non_sale_ratio)  # 분양면적
        # 혼잡도 개선 (간이 모델)
        predicted_cong = max(0.0, congestion_base * (1 - bus_inc_pct / 150))
        cong_improve = max(0.0, congestion_base - predicted_cong)

        # 매출/비용 (만원 단위 -> 억원 환산)
        revenue_won = sellable_m2 * sale_price_per_m2 * sale_rate  # (만원)
        cost_won = sellable_m2 * build_cost_per_m2                 # (만원)
        total_cost_bil = cost_won/1e4/100 + infra_invest_billion   # (억원)
        total_rev_bil  = revenue_won/1e4/100                       # (억원)

        profit_bil = total_rev_bil - total_cost_bil
        margin_pct = (profit_bil / total_cost_bil * 100) if total_cost_bil>0 else 0

        # 간이 NPV (균등현금흐름 가정)
        cf_annual = profit_bil / years
        npv = sum([cf_annual / ((1+disc_rate)**t) for t in range(1, years+1)])
        payback = min(years, max(1, int(np.ceil(total_cost_bil / max(1e-6, cf_annual)))))

        return {
            "분양면적(㎡)": sellable_m2,
            "예상혼잡도(%)": round(predicted_cong,1),
            "혼잡도개선(Δ%)": round(cong_improve,1),
            "총매출(억원)": round(total_rev_bil,1),
            "총사업비(억원)": round(total_cost_bil,1),
            "이익(억원)": round(profit_bil,1),
            "마진율(%)": round(margin_pct,1),
            "NPV(억원)": round(npv,1),
            "회수기간(년)": payback,
        }

    # ---------------------------
    # 1) 입력/시나리오 탭
    # ---------------------------
    tab1, tab2, tab3, tab4 = st.tabs(["🧩 입력·시나리오", "📈 민감도", "🎲 확률(간이)", "📤 리포트"])

    with tab1:
        st.markdown("#### 📋 공통 입력")
        c1, c2 = st.columns(2)
        with c1:
            households = int(st.number_input("계획 세대수", 100, 10000, int(current.get("households") or 1000), step=50))
            avg_py = st.number_input("평균 전용면적(평)", 10.0, 60.0, float(st.session_state.get("desired_py", 25.0)), 0.5)
            congestion_base = st.number_input("기준 혼잡도(%)", 0.0, 100.0, 50.0, 1.0)
            non_sale_ratio = st.slider("비분양 비율", 0.0, 0.4, 0.15, 0.01, help="공공/커뮤니티 등")
        with c2:
            sale_rate = st.slider("분양률", 0.80, 1.00, 0.98, 0.01)
            disc_rate = st.slider("할인율(재무)", 0.03, 0.15, 0.07, 0.005)
            years = st.slider("회수기간(년)", 2, 10, 4, 1)
            base_bus_inc = st.slider("베이스라인 버스 증편(%)", 0, 100, 10, 5)

        st.markdown("#### 🧪 시나리오 정의")
        st.caption("분양가/공사비/버스증편/인프라투자만 다르게 하며, 나머지는 공통 입력을 상속합니다.")
        def scenario_inputs(label, sale_default, cost_default, bus_default, infra_default):
            a, b, c, d = st.columns(4, gap="small")
            with a:
                sale = st.number_input(f"{label}·분양가(만원/㎡)", 500.0, 3000.0, sale_default, 10.0, key=f"sale_{label}")
            with b:
                cost = st.number_input(f"{label}·공사비(만원/㎡)", 300.0, 2500.0, cost_default, 10.0, key=f"cost_{label}")
            with c:
                bus = st.slider(f"{label}·버스증편(%)", 0, 100, bus_default, 5, key=f"bus_{label}")
            with d:
                infra = st.number_input(f"{label}·인프라(억원)", 0.0, 1000.0, infra_default, 5.0, key=f"infra_{label}")
            return sale, cost, bus, infra

        saleA, costA, busA, infraA = scenario_inputs("A", 1200.0, 900.0, base_bus_inc, 30.0)
        saleB, costB, busB, infraB = scenario_inputs("B", 1300.0, 950.0, base_bus_inc+10, 50.0)
        saleC, costC, busC, infraC = scenario_inputs("C", 1100.0, 850.0, max(0, base_bus_inc-5), 20.0)

        scenarios = {
            "A": dict(sale=saleA, cost=costA, bus=busA, infra=infraA),
            "B": dict(sale=saleB, cost=costB, bus=busB, infra=infraB),
            "C": dict(sale=saleC, cost=costC, bus=busC, infra=infraC),
        }

        # KPI 계산 & 비교표
        import pandas as pd
        rows = []
        for name, s in scenarios.items():
            k = calc_kpis(
                households, avg_py, s["sale"], s["cost"], s["infra"],
                congestion_base, s["bus"], non_sale_ratio, sale_rate, disc_rate, years
            )
            rows.append({"시나리오": name, **k})
        df_scn = pd.DataFrame(rows).set_index("시나리오")

        st.markdown("#### 📊 시나리오 비교표")
        st.dataframe(df_scn, use_container_width=True)

        # 하이라이트 카드
        best = df_scn.sort_values("NPV(억원)", ascending=False).head(1)
        st.success(f"**추천 시나리오: {best.index[0]}** · NPV {best['NPV(억원)'].iloc[0]:,.1f}억원 · 마진율 {best['마진율(%)'].iloc[0]:.1f}%")

    # ---------------------------
    # 2) 민감도 (토네이도 차트)
    # ---------------------------
    with tab2:
        st.markdown("#### 📈 민감도 분석 (토네이도)")
        base_sale = st.number_input("기준 분양가(만원/㎡)", 500.0, 3000.0, 1200.0, 10.0)
        base_cost = st.number_input("기준 공사비(만원/㎡)", 300.0, 2500.0, 900.0, 10.0)
        base_bus  = st.slider("기준 버스증편(%)", 0, 100, 20, 5)
        base_infra= st.number_input("기준 인프라(억원)", 0.0, 1000.0, 30.0, 5.0)

        # ±변동폭
        pct = st.slider("변동폭(±%)", 1, 30, 15, 1)

        def kpi_with(sale, cost, bus, infra):
            return calc_kpis(households, avg_py, sale, cost, infra, congestion_base, bus,
                             non_sale_ratio, sale_rate, disc_rate, years)["NPV(억원)"]

        import numpy as np, altair as alt
        base_npv = kpi_with(base_sale, base_cost, base_bus, base_infra)
        factors = []
        for name, (lo, hi) in {
            "분양가": (base_sale*(1-pct/100), base_sale*(1+pct/100)),
            "공사비": (base_cost*(1-pct/100), base_cost*(1+pct/100)),
            "버스증편": (max(0, base_bus-pct), min(100, base_bus+pct)),
            "인프라": (max(0, base_infra*(1-pct/100)), base_infra*(1+pct/100)),
        }.items():
            npv_lo = kpi_with(lo if name=="분양가" else base_sale,
                              lo if name=="공사비" else base_cost,
                              lo if name=="버스증편" else base_bus,
                              lo if name=="인프라" else base_infra)
            npv_hi = kpi_with(hi if name=="분양가" else base_sale,
                              hi if name=="공사비" else base_cost,
                              hi if name=="버스증편" else base_bus,
                              hi if name=="인프라" else base_infra)
            factors.append({"요인": name, "NPV_low": npv_lo, "NPV_high": npv_hi})

        df_tornado = pd.DataFrame(factors)
        bars = alt.Chart(df_tornado).transform_fold(
            ["NPV_low","NPV_high"], as_=["type","NPV"]
        ).mark_bar().encode(
            y=alt.Y("요인:N", sort=None),
            x=alt.X("NPV:Q", title="NPV(억원)"),
            color="type:N",
            tooltip=["요인:N","NPV:Q"]
        ).properties(height=200)
        st.altair_chart(bars, use_container_width=True)


    # ---------------------------
    # 3) 확률(간이) Monte Carlo
    # ---------------------------
    with tab3:
        st.markdown("#### 🎲 확률 분석 (간이 Monte Carlo)")
        n = st.slider("시뮬레이션 반복수", 200, 5000, 1000, 100)
        sigma_sale = st.slider("분양가 표준편차(%)", 1, 20, 7)
        sigma_cost = st.slider("공사비 표준편차(%)", 1, 20, 5)

        rng = np.random.default_rng(42)
        sale_samples = rng.normal(loc=base_sale, scale=base_sale*sigma_sale/100, size=n)
        cost_samples = rng.normal(loc=base_cost, scale=base_cost*sigma_cost/100, size=n)

        npvs = []
        for s, c in zip(sale_samples, cost_samples):
            npvs.append(kpi_with(max(100, s), max(100, c), base_bus, base_infra))
        ser = pd.Series(npvs)
        p10, p50, p90 = np.percentile(ser, [10,50,90])

        st.metric("P10 NPV", f"{p10:,.1f} 억원")
        st.metric("P50 NPV", f"{p50:,.1f} 억원")
        st.metric("P90 NPV", f"{p90:,.1f} 억원")
        st.caption("※ P10: 보수적(하위 10%), P90: 낙관적(상위 10%)")

        hist = alt.Chart(pd.DataFrame({"NPV": ser})).mark_bar().encode(
            x=alt.X("NPV:Q", bin=alt.Bin(maxbins=30), title="NPV(억원)"),
            y="count()"
        ).properties(height=200)
        st.altair_chart(hist, use_container_width=True)

    # ---------------------------
    # 4) 리포트/체크리스트
    # ---------------------------
    with tab4:
        st.markdown("#### 🧷 행정 협의 체크리스트 (자동 생성)")
        imp = float(df_scn.loc["A","혼잡도개선(Δ%)"]) if "A" in df_scn.index else 0.0
        msg = []
        if imp >= 5:
            msg.append("• 교통영향평가 협의 시, **혼잡도 개선 Δ≥5%** 근거 제시 (버스 증편 + 노선 최적화)")
        else:
            msg.append("• 혼잡도 개선이 작음 → **정류장 위치/환승편의** 시뮬레이션 보완 권고")
        if df_scn["마진율(%)"].max() < 10:
            msg.append("• 마진율 낮음 → 공사비 단가/평형 믹스/비분양 비율 재검토 권고")
        if df_scn["NPV(억원)"].max() < 0:
            msg.append("• NPV 음수 → 분양가 산정 재검토 또는 인프라 투자 축소 필요")
        st.write("\n".join(msg))

        st.markdown("#### 📤 내보내기")
        export_df = df_scn.reset_index()
        st.download_button("⬇️ 시나리오 비교표(CSV)", data=export_df.to_csv(index=False).encode("utf-8-sig"),
                           file_name="scenario_compare.csv", mime="text/csv")

        # 간단 PDF (텍스트 위주)
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors

        def export_pdf_simple():
            path = "AIoT_Biz_Analysis_Report.pdf"
            styles = getSampleStyleSheet()
            doc = SimpleDocTemplate(path, pagesize=A4)
            story = [
                Paragraph("AIoT 스마트 인프라 대시보드 — 사업성 분석 리포트", styles["Title"]),
                Spacer(1, 12),
                Paragraph(f"대상: {current.get('address_display','')}", styles["Normal"]),
                Paragraph(f"자치구: {current.get('gu','')}", styles["Normal"]),
                Spacer(1, 12),
                Paragraph("시나리오 비교 요약", styles["Heading2"]),
            ]
            # 표 데이터
            tbl_data = [export_df.columns.tolist()] + export_df.astype(str).values.tolist()
            tbl = Table(tbl_data, repeatRows=1)
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.black),
                ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
                ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
                ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ]))
            story += [tbl, Spacer(1, 12)]
            story += [Paragraph("행정 협의 체크포인트", styles["Heading2"])]
            for t in msg:
                story += [Paragraph(t, styles["Normal"])]
            story += [Spacer(1, 12), Paragraph("가정/파라미터 로그", styles["Heading2"])]
            story += [Paragraph(f"세대수={households:,}, 평균전용={avg_py}평, 비분양={int(non_sale_ratio*100)}%, 분양률={int(sale_rate*100)}%", styles["Normal"])]
            story += [Paragraph(f"할인율={disc_rate*100:.1f}%, 회수기간={years}년, 기준혼잡도={congestion_base}%", styles["Normal"])]
            doc.build(story)
            return path

        if st.button("📄 PDF 리포트 다운로드"):
            pdf_path = export_pdf_simple()
            st.success(f"PDF 생성 완료: {pdf_path}")
