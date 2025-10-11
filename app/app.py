# -------------------------------------------------------------
# 🏗 AIoT 스마트 인프라 대시보드 (재건축 의사결정 Helper) — OPTIMIZED
# -------------------------------------------------------------
# 주요 개선점
# - 중복 import/변수 제거, 상수 일원화
# - 대용량 리소스(Shapefile/교통CSV) 캐싱(@st.cache_resource / @st.cache_data)
# - GeoJSON 세션 저장 최소화: 세션에는 "키"만 저장하고, 실데이터는 캐시에서 참조
# - dtype 최적화(category/numeric 다운캐스트)로 메모리 절감
# - 공통 계산(혼잡도 변환/일평균/시그모이드CFI 등) 함수화 + 재사용
# - 방어적 코딩(결측/부재 파일 처리), 불필요한 데이터프레임 복제 제거
# - 레이아웃/Altair 렌더 분리로 불필요한 재계산 최소화
# -------------------------------------------------------------

import sys
from pathlib import Path
import json
import numpy as np
import pandas as pd
import geopandas as gpd
import pydeck as pdk
import altair as alt
import streamlit as st
import numpy_financial as npf  # (향후 재무모델 확장 대비)
from datetime import datetime

# ────────────────────────────────────────────────────────────────
# 경로/상수
# ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent  # .../seoul_dashboard_3
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

DATA_DIR = BASE_DIR / "data"
BASE_YEAR = 2023  # 기준년도

# 파일 경로
PROJECTS_CSV_PATH = DATA_DIR / "seoul_redev_projects.csv"
TRAFFIC_XLSX_PATH = DATA_DIR / "AverageSpeed(LINK).xlsx"
TRAFFIC_CSV_PATH  = DATA_DIR / f"AverageSpeed(LINK)_{BASE_YEAR}.csv"  # ✅ 누락 보완
TRAFFIC_VOL_CSV_PATH = DATA_DIR / f"TrafficVolume_Seoul_{BASE_YEAR}.csv"
SHP_PATH = DATA_DIR / "seoul_link_lev5.5_2023.shp"
LINK_ID_COL = "k_link_id"

# 외부 유틸
from components.sidebar_presets import render_sidebar_presets
from components.sidebar_4quadrant_guide import render_sidebar_4quadrant_guide
from utils.traffic_preproc import ensure_speed_csv

# plot_speed 있으면 활용, 없으면 fallback
try:
    from utils.traffic_plot import plot_speed
    _HAS_PLOT_SPEED = True
except Exception:
    from utils.traffic_plot import plot_nearby_speed_from_csv as plot_speed_fallback
    _HAS_PLOT_SPEED = False

# ────────────────────────────────────────────────────────────────
# Streamlit 설정 & 전역 스타일
# ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="AIoT 스마트 인프라 대시보드 | 재건축 Helper", layout="wide")

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
.kpi-value { font-size: 1.4rem; font-weight: 700; color: #e5e7eb; }
.section-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 8px; }
hr.soft { border: none; height: 1px; background: #1f2937; margin: 16px 0; }
</style>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────────
# 세션 초기화 (필요 키만)
# ────────────────────────────────────────────────────────────────
for k, v in {
    "matched_geo_key_daily": None,     # 캐시된 GeoJSON의 키 (실데이터는 캐시에 존재)
    "matched_geo_key_hourly": None,    # (미사용시 None 유지)
    "color_mode_daily_val": "절대(30/70)",
    "selected_row": None,
    "selected_gu_prev": None,
    "eta_by_gu": {},
}.items():
    st.session_state.setdefault(k, v)

# 캐시 비우기
with st.sidebar:
    if st.button("캐시 비우기"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.session_state["matched_geo_key_daily"] = None
        st.session_state["matched_geo_key_hourly"] = None
        st.rerun()

# ────────────────────────────────────────────────────────────────
# 보조 유틸
# ────────────────────────────────────────────────────────────────
def smart_read_csv(path, encodings=("utf-8-sig", "cp949", "euc-kr", "utf-8", "latin1")) -> pd.DataFrame:
    last_err = None
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError as e:
            last_err = e
    try:
        return pd.read_csv(path, encoding="utf-8", errors="replace")
    except Exception:
        raise last_err or Exception(f"Failed to read {path}")

def _downcast_numeric(df: pd.DataFrame, exclude: set[str] = frozenset()) -> pd.DataFrame:
    # 수치형 다운캐스트로 메모리 절감
    for c in df.columns:
        if c in exclude:
            continue
        if pd.api.types.is_integer_dtype(df[c]):
            df[c] = pd.to_numeric(df[c], downcast="integer")
        elif pd.api.types.is_float_dtype(df[c]):
            df[c] = pd.to_numeric(df[c], downcast="float")
    return df

def _categorify(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = df[c].astype("category")
    return df

# ────────────────────────────────────────────────────────────────
# 데이터 로딩 & 정규화 (캐싱)
# ────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_raw_projects() -> pd.DataFrame:
    df = smart_read_csv(PROJECTS_CSV_PATH)
    return df

def _pct_to_num(s):
    s = pd.Series(s).astype(str).str.replace("%", "", regex=False).str.replace(",", "", regex=False)
    return pd.to_numeric(s, errors="coerce")

def _floors_to_num(s):
    return pd.to_numeric(pd.Series(s).astype(str).str.extract(r"(-?\d+)", expand=False), errors="coerce")

@st.cache_data(show_spinner=False)
def normalize_projects(df_raw: pd.DataFrame) -> pd.DataFrame:
    c = df_raw.columns
    get = lambda name: df_raw[name] if name in c else pd.Series([None]*len(df_raw))

    df = pd.DataFrame({
        "apt_id": get("사업번호"),
        "name": [v if (pd.notna(v) and str(v).strip()) else w for v, w in zip(get("정비구역명칭"), get("추진위원회/조합명"))],
        "org_name": get("추진위원회/조합명"),
        "biz_type": get("사업구분"),
        "op_type": get("운영구분"),
        "gu": get("자치구"),
        "address": [v if (pd.notna(v) and str(v).strip()) else w for v, w in zip(get("정비구역위치"), get("대표지번"))],
        "households": pd.to_numeric(get("분양세대총수"), errors="coerce"),
        "land_area_m2": pd.to_numeric(get("정비구역면적(㎡)"), errors="coerce"),
        "far": _pct_to_num(get("용적률")),
        "floors": _floors_to_num(get("층수")),
        "status": get("진행단계"),
        "floors_up": _floors_to_num(get("지상층수")),
        "floors_down": _floors_to_num(get("지하층수")),
    })
    def _fmt_floor(u, d):
        parts = []
        if pd.notna(u): parts.append(f"지상 {int(u)}")
        if pd.notna(d): parts.append(f"지하 {int(d)}")
        return " / ".join(parts)

    df["floors_display"] = [_fmt_floor(u, d) for u, d in zip(df["floors_up"], df["floors_down"])]
    df["floors_show"] = df["floors_display"].fillna("").astype(str).str.strip()
    mask_empty = df["floors_show"] == ""
    df.loc[mask_empty, "floors_show"] = df.loc[mask_empty, "floors"].apply(lambda x: f"{int(x)}층" if pd.notna(x) else "")

    # 정리/타입 최적화
    df["apt_id"] = df["apt_id"].astype(str)
    df["name"]   = df["name"].fillna("무명 정비구역")
    for col in ["org_name","biz_type","op_type","gu","address","status"]:
        df[col] = df[col].fillna("").astype(str).str.strip()
    df = _downcast_numeric(df)
    df = _categorify(df, ["gu","biz_type","op_type","status"])
    return df

@st.cache_data(show_spinner=False)
def load_coords() -> pd.DataFrame:
    path = DATA_DIR / "서울시_재개발재건축_clean_kakao.csv"
    df = smart_read_csv(path)
    # 안전 숫자화
    df["lat"] = pd.to_numeric(df.get("lat"), errors="coerce")
    df["lon"] = pd.to_numeric(df.get("lon"), errors="coerce")

    def _coalesce(a,b):
        a = "" if a is None else str(a).strip()
        b = "" if b is None else str(b).strip()
        return a if a else b

    if ("정비구역명칭" in df.columns) or ("추진위원회/조합명" in df.columns):
        name = [_coalesce(n, m) for n, m in zip(df.get("정비구역명칭"), df.get("추진위원회/조합명"))]
    else:
        name = df.get("name")

    address = [_coalesce(a, b) for a, b in zip(df.get("정비구역위치"), df.get("대표지번"))]

    out = pd.DataFrame({
        "apt_id": df.get("사업번호").astype(str) if "사업번호" in df.columns else "",
        "name": pd.Series(name, index=df.index),
        "gu": df.get("자치구"),
        "address": pd.Series(address, index=df.index),
        "full_address": df.get("full_address"),
        "lat": df["lat"], "lon": df["lon"],
    })
    for col in ["apt_id","name","gu","address","full_address"]:
        if col in out.columns:
            out[col] = out[col].fillna("").astype(str).str.strip()
    out = _downcast_numeric(out)
    out = _categorify(out, ["gu"])
    return out

@st.cache_data(show_spinner=False)
def projects_by_gu(gu: str) -> pd.DataFrame:
    return normalize_projects(load_raw_projects()).query("gu == @gu").reset_index(drop=True)

# ────────────────────────────────────────────────────────────────
# 지오 데이터 (Shapefile/교통CSV) 로딩 (리소스 캐시)
# ────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def load_links_gdf() -> gpd.GeoDataFrame | None:
    if not SHP_PATH.exists():
        return None
    gdf = gpd.read_file(SHP_PATH, columns=[LINK_ID_COL, "geometry"])
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    gdf["link_id_norm"] = gdf[LINK_ID_COL].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    return gdf[[ "link_id_norm", "geometry" ]]

@st.cache_data(show_spinner=False)
def load_speed_csv_from_xlsx_if_needed():
    # 엑셀을 CSV로 변환해두고 CSV 로드(없으면 경고)
    if TRAFFIC_XLSX_PATH.exists():
        ensure_speed_csv(TRAFFIC_XLSX_PATH, TRAFFIC_CSV_PATH)

@st.cache_data(show_spinner=False)
def load_volume_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df["link_id"] = df["link_id"].astype(str)
    h = pd.to_numeric(pd.Series(df["hour"]).astype(str).str.extract(r"(\d+)", expand=False), errors="coerce").fillna(0).astype(int) % 24
    df["hour"] = h
    df["차량대수"] = pd.to_numeric(df["차량대수"], errors="coerce").fillna(0)
    return _downcast_numeric(df)

# ────────────────────────────────────────────────────────────────
# 지도/혼잡 계산 유틸
# ────────────────────────────────────────────────────────────────
def color_by_value(v: float):
    if pd.isna(v): return (200,200,200)
    v = float(v)
    if v < 30: return (0,200,0)
    if v < 70: return (255,200,0)
    return (255,0,0)

def color_by_quantile(v: float, q30: float, q70: float):
    if pd.isna(v): return (200,200,200)
    if v < q30: return (0,200,0)
    if v < q70: return (255,200,0)
    return (255,0,0)

def compute_congestion_from_speed(df_plot: pd.DataFrame) -> pd.DataFrame:
    # 속도→혼잡% (0=자유, 100=매우혼잡)
    d = df_plot.copy()
    d["평균속도(km/h)"] = pd.to_numeric(d["평균속도(km/h)"], errors="coerce")
    d["free_flow"] = d.groupby("link_id")["평균속도(km/h)"].transform("max").clip(lower=1)
    d["value"] = ((1 - (d["평균속도(km/h)"] / d["free_flow"]).clip(0, 1)) * 100).clip(0, 100)
    return d[["link_id","hour","value"]]

@st.cache_data(show_spinner=False)
def build_daily_geojson_key(
    df_daily: pd.DataFrame,
    color_mode: str
) -> str:
    """
    df_daily: columns [link_id, daily_value]
    캐시에 GeoJSON 객체를 저장하고, session에는 그 키만 보관.
    """
    links_gdf = load_links_gdf()  # 🔁 캐시된 리소스를 내부에서 사용 (unhashable 인자 전달 X)
    if links_gdf is None or df_daily.empty:
        return ""

    gdf = links_gdf.merge(
        df_daily.assign(
            link_id_norm=df_daily["link_id"].astype(str).str.replace(r"\.0$","",regex=True).str.strip()
        ),
        on="link_id_norm",
        how="inner"
    )
    if gdf.empty:
        return ""

    if color_mode.startswith("상대"):
        q30 = float(np.nanpercentile(gdf["daily_value"], 30))
        q70 = float(np.nanpercentile(gdf["daily_value"], 70))
        cols = list(zip(*gdf["daily_value"].apply(lambda x: color_by_quantile(x, q30, q70))))
    else:
        cols = list(zip(*gdf["daily_value"].apply(color_by_value)))

    gdf["color_r"], gdf["color_g"], gdf["color_b"] = cols[0], cols[1], cols[2]
    gdf["tooltip_html"] = (
        "<b>링크:</b> " + gdf["link_id_norm"].astype(str)
        + "<br/><b>일평균 혼잡도:</b> " + gdf["daily_value"].round(1).astype(str) + "%"
    )
    geojson_obj = json.loads(gdf.to_json())

    # 키는 간단 해시(행수+평균값+모드)
    key = f"{len(gdf)}_{round(float(gdf['daily_value'].mean()),2)}_{'rel' if color_mode.startswith('상대') else 'abs'}"
    _geojson_cache_store(key, geojson_obj)
    return key


# 간단한 내부 캐시(dict) — st.cache_data 내부 상태(세션 외부)로 저장
@st.cache_resource(show_spinner=False)
def _geojson_store() -> dict:
    # 세션 동안 살아있는 변경 가능한 저장소
    return {}

def _geojson_cache_store(key: str, obj: dict) -> bool:
    _geojson_store()[key] = obj
    return True

def _geojson_cache_get(key: str) -> dict | None:
    return _geojson_store().get(key)


# ────────────────────────────────────────────────────────────────
# 기타 상수
# ────────────────────────────────────────────────────────────────
DISTRICTS = [
    "강남구","강동구","강북구","강서구","관악구","광진구","구로구","금천구",
    "노원구","도봉구","동대문구","동작구","마포구","서대문구","서초구","성동구",
    "성북구","송파구","양천구","영등포구","용산구","은평구","종로구","중구","중랑구"
]
GU_CENTER = {
    "강남구": (37.5172, 127.0473), "강동구": (37.5301, 127.1238), "강북구": (37.6396, 127.0257),
    "강서구": (37.5509, 126.8495), "관악구": (37.4784, 126.9516), "광진구": (37.5386, 127.0822),
    "구로구": (37.4955, 126.8876), "금천구": (37.4569, 126.8958), "노원구": (37.6543, 127.0565),
    "도봉구": (37.6688, 127.0471), "동대문구": (37.5740, 127.0396), "동작구": (37.5124, 126.9393),
    "마포구": (37.5638, 126.9084), "서대문구": (37.5791, 126.9368), "서초구": (37.4836, 127.0326),
    "성동구": (37.5633, 127.0369), "성북구": (37.5894, 127.0167), "송파구": (37.5145, 127.1068),
    "양천구": (37.5169, 126.8665), "영등포구": (37.5264, 126.8963), "용산구": (37.5311, 126.9811),
    "은평구": (37.6176, 126.9227), "종로구": (37.5736, 126.9780), "중구": (37.5636, 126.9976),
    "중랑구": (37.6063, 127.0929),
}
SENS_DEFAULTS = {
    "강남구": 0.75, "서초구": 0.70, "송파구": 0.65, "강동구": 0.60,
    "마포구": 0.55, "용산구": 0.65, "영등포구": 0.60, "동작구": 0.55,
    "관악구": 0.55, "광진구": 0.55, "성동구": 0.60, "강서구": 0.50,
    "양천구": 0.55, "구로구": 0.50, "금천구": 0.50, "동대문구": 0.55,
    "중랑구": 0.50, "성북구": 0.55, "강북구": 0.50, "도봉구": 0.50,
    "노원구": 0.55, "서대문구": 0.55, "은평구": 0.50, "종로구": 0.60, "중구": 0.60,
}

# ✅ [새로 추가] 새벽 완급 함수
def apply_dawn_smoothing(w_hour: np.ndarray, *, min_factor: float = 0.55, turn_hour: float = 7.5, k: float = 0.9) -> np.ndarray:
    """
    w_hour: 길이 24, 0~23시 가중치
    min_factor: 심야(0~3시) 최소 비율
    turn_hour: 회복 중심 시각(예: 7.5 = 07:30)
    k: 시그모이드 기울기
    """
    h = np.arange(24, dtype=float)
    dawn_curve = min_factor + (1.0 - min_factor) / (1.0 + np.exp(-k * (h - turn_hour)))
    return w_hour * dawn_curve

# 기존코드 <- (기타 상수 블록 끝 부분에 추가)
ALPHA_HOURLY = 1.5
EPS_HOURLY   = 0.05

# >>> PATCH B: mitigation solver (uniform bus% to make after<=base) ---
BUS_COST_PER_1PCT_BIL_DEFAULT = 2.0   # 1% 증편에 드는 연간 비용(억원)·예시값

def compute_min_bus_increase_to_cap(after: np.ndarray, base: np.ndarray) -> float:
    """
    '재건축 후' 곡선(after)을 선형 감쇠 계수 (1 - b/150)로 낮춰
    모든 시간대에서 base 이하가 되도록 하는 최소 b(%)를 반환.
    - after_adj(h) = after(h) * (1 - b/150)
    - 제약: after_adj(h) <= base(h) for all h
    해를 닫힌형으로 구하면:
      b >= 150 * max_h max(0, 1 - base(h)/max(after(h), 1e-6))
    """
    a = np.maximum(after.astype(float), 1e-6)
    b = base.astype(float)
    ratio = 1.0 - (b / a)
    need = np.maximum(0.0, ratio).max()
    return float(np.clip(150.0 * need, 0.0, 100.0))  # 0~100%로 클립
# ---------------------------------------------------------------------



# ────────────────────────────────────────────────────────────────
# 사이드바
# ────────────────────────────────────────────────────────────────
st.sidebar.title("재건축 의사결정 Helper")

selected_gu = st.sidebar.selectbox("구 선택", DISTRICTS, index=0)
if st.session_state["selected_gu_prev"] != selected_gu:
    st.session_state["selected_row"] = None
    st.session_state["selected_gu_prev"] = selected_gu

st.sidebar.markdown("<div class='small-muted'>구 선택 시, 해당 구의 정비사업 단지 목록과 지도가 갱신됩니다.</div>", unsafe_allow_html=True)
project_name = st.sidebar.text_input("프로젝트 이름", value=f"{selected_gu} 재건축 시나리오")

render_sidebar_presets()
render_sidebar_4quadrant_guide()

# ────────────────────────────────────────────────────────────────
# 1–2 사분면: 지도 & 단지 선택
# ────────────────────────────────────────────────────────────────
col12_left, col12_right = st.columns([2.2, 1.4], gap="large")
with col12_left:
    st.markdown("### 🗺 [1-2사분면] · 지도 & 단지선택")

    base_df = projects_by_gu(selected_gu)

    # 좌표 병합 (name+gu 기준). 좌표 없음 → 구 중심 + jitter
    coords = load_coords().query("gu == @selected_gu").copy()
    df_map = base_df.merge(
        coords[["name","gu","lat","lon","full_address"]],
        on=["name","gu"], how="left"
    )
    miss = df_map["lat"].isna() | df_map["lon"].isna()
    if miss.any():
        base_lat, base_lon = GU_CENTER.get(selected_gu, (37.55, 127.0))
        rng = np.random.default_rng(42)
        df_map.loc[miss, "lat"] = base_lat + rng.normal(0, 0.002, int(miss.sum()))
        df_map.loc[miss, "lon"] = base_lon + rng.normal(0, 0.002, int(miss.sum()))
    df_map["has_geo"] = ~miss
    df_map["address_display"] = df_map["full_address"].fillna("").replace("", pd.NA)
    df_map["address_display"] = df_map["address_display"].fillna(df_map["address"]).fillna("")

    # 메모리 절감
    df_map = _downcast_numeric(df_map)
    df_map = _categorify(df_map, ["gu","biz_type","op_type","status"])

    map_slot = st.empty()
    if df_map.empty:
        st.warning("⚠️ 해당 구에 데이터가 없습니다.")
        st.stop()

with st.expander("🔍 데이터 소스 확인(임시)", expanded=False):
    raw = load_raw_projects()
    cols_raw = ["자치구", "정비구역명칭", "추진위원회/조합명", "분양세대총수", "정비구역면적(㎡)"]
    exist = [c for c in cols_raw if c in raw.columns]
    st.caption(f"원본: {PROJECTS_CSV_PATH.name} · 표시열: {', '.join(exist)}")
    try:
        st.dataframe(raw[exist][raw["자치구"] == selected_gu].head(20), use_container_width=True)
    except Exception:
        st.dataframe(raw[exist].head(20), use_container_width=True)
    st.caption("현재 표시값(df_map)")
    st.dataframe(df_map[["gu","address_display","name","households","land_area_m2"]].head(20), use_container_width=True)

st.markdown("**단지 목록**")
df_list = df_map[[
    "apt_id","address_display","org_name","biz_type","op_type","status",
    "households","land_area_m2","far","floors_show"
]].copy()

# 숫자형 정리
for col in ["households","land_area_m2","far"]:
    df_list[col] = pd.to_numeric(df_list[col], errors="coerce")

# 필터 UI
fcol1, fcol2, fcol3, fcol4 = st.columns([1.6,1.4,1.6,1.2])
with fcol1:
    kw = st.text_input("검색어(주소/조합명/키워드)", value="", placeholder="예) 개포, 목동, 조합")

HH_BUCKETS = {
    "전체": (None, None), "~ 300세대": (0, 300), "301–500세대": (301, 500),
    "501–1,000세대": (501, 1000), "1,001–2,000세대": (1001, 2000), "2,001세대 이상": (2001, None),
}
AREA_BUCKETS = {
    "전체": (None, None), "~ 30,000 m²": (0, 30000), "30,001–50,000 m²": (30001, 50000),
    "50,001–100,000 m²": (50001, 100000), "100,001–200,000 m²": (100001, 200000), "200,001 m² 이상": (200001, None),
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
hh_lo, hh_hi = HH_BUCKETS[hh_choice]; la_lo, la_hi = AREA_BUCKETS[la_choice]
if hh_lo is not None: mask &= df_list["households"].fillna(-1) >= hh_lo
if hh_hi is not None: mask &= df_list["households"].fillna(-1) <= hh_hi
if la_lo is not None: mask &= df_list["land_area_m2"].fillna(-1) >= la_lo
if la_hi is not None: mask &= df_list["land_area_m2"].fillna(-1) <= la_hi
if hide_zero:
    mask &= df_list["households"].fillna(0) > 0
    mask &= df_list["land_area_m2"].fillna(0) > 0

filtered = df_list[mask].reset_index().rename(columns={"index":"orig_index"})
scol1, scol2 = st.columns([1.2,1.2])
with scol1:
    sort_key = st.selectbox("정렬 기준",
        ["세대수 내림차순","세대수 오름차순","면적 내림차순","면적 오름차순","주소 오름차순"], index=0)
with scol2:
    topn = st.selectbox("표시 개수", [10,20,50,100,"전체"], index=1)
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
    "orig_index","address_display","org_name","biz_type","op_type","status",
    "households","land_area_m2","far","floors_show"
]].copy().rename(columns={
    "address_display":"주소","org_name":"추진위원회/조합명","biz_type":"사업구분",
    "op_type":"운영구분","status":"진행단계","households":"계획세대수",
    "land_area_m2":"면적","far":"용적률(%)","floors_show":"층수"
})
show_df.insert(1, "선택", False)

curr_ids = show_df["orig_index"].tolist()
if (st.session_state["selected_row"] is None) or (st.session_state["selected_row"] not in curr_ids):
    st.session_state["selected_row"] = int(curr_ids[0]) if curr_ids else None
show_df.loc[show_df["orig_index"] == st.session_state["selected_row"], "선택"] = True

edited = st.data_editor(
    show_df, use_container_width=True, hide_index=True,
    disabled=["orig_index","주소","추진위원회/조합명","사업구분","운영구분","진행단계","계획세대수","면적","용적률(%)","층수"],
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

prev = st.session_state["selected_row"]
sel_list = [int(x) for x in edited.loc[edited["선택"] == True, "orig_index"].tolist()]
if len(sel_list) == 0:
    st.session_state["selected_row"] = int(prev) if prev in curr_ids else (int(curr_ids[0]) if curr_ids else None)
elif len(sel_list) == 1:
    st.session_state["selected_row"] = int(sel_list[0])
else:
    st.session_state["selected_row"] = int(sel_list[0] if prev not in sel_list else next((x for x in sel_list if x != prev), sel_list[0]))
    st.rerun()

if st.session_state["selected_row"] is None:
    st.info("선택된 행이 없습니다.")
    st.stop()
selected_row = st.session_state["selected_row"]

current = df_map.loc[selected_row]
st.session_state["selected_site"] = current["name"]

# 지도 렌더 준비
filtered_indices = edited["orig_index"].tolist()
map_data = df_map.loc[filtered_indices, ["lat","lon","address_display","gu","households","land_area_m2"]].copy()

def _point_tooltip(row):
    return (f"<b>{row.get('address_display','')}</b><br/>"
            f"자치구: {row.get('gu','')}<br/>"
            f"세대수: {row.get('households','')}<br/>"
            f"구역면적(m²): {row.get('land_area_m2','')}")
map_data["tooltip_html"] = map_data.apply(_point_tooltip, axis=1)

highlight_row = df_map.loc[[selected_row], ["lat","lon","address_display","gu","households","land_area_m2"]].copy()
highlight_row["tooltip_html"] = highlight_row.apply(_point_tooltip, axis=1)

sel_lat, sel_lon = float(current["lat"]), float(current["lon"])
view_state = pdk.ViewState(latitude=sel_lat, longitude=sel_lon, zoom=12.5)

layer_points = pdk.Layer(
    "ScatterplotLayer", data=map_data, get_position='[lon, lat]', get_radius=60,
    pickable=True, get_fill_color=[255,140,0,160], get_line_color=[255,255,255], line_width_min_pixels=0.5,
)
layer_highlight = pdk.Layer(
    "ScatterplotLayer", data=highlight_row, get_position='[lon, lat]', get_radius=150,
    pickable=False, get_fill_color=[0,200,255,220], get_line_color=[0,0,0], line_width_min_pixels=1.2,
)
tooltip = {"html":"{tooltip_html}", "style":{"backgroundColor":"#0f172a", "color":"white"}}

def render_map(initial_view_state):
    layers = []
    key_daily = st.session_state.get("matched_geo_key_daily")
    if key_daily:
        gj = _geojson_cache_get(key_daily)
        if gj:
            layers.append(pdk.Layer(
                "GeoJsonLayer",
                data=gj,
                pickable=True,
                auto_highlight=True,
                get_line_color='[properties.color_r, properties.color_g, properties.color_b, 220]',
                get_line_width=2,  # 선 굵기 지정
                line_width_min_pixels=2,  # 최소 픽셀 굵기 (snake_case)
            ))

    layers += [layer_points, layer_highlight]
    map_slot.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=initial_view_state, tooltip=tooltip))

with col12_right:
    st.markdown("### 🧾 [1사분면] · 기존 단지 정보")
    with st.container(border=True):
        st.markdown("**기존 단지 정보**")
        st.markdown(
            f"- 주소: **{current['address_display']}**\n\n"
            f"- 추진위원회/조합명: **{current['org_name']}**\n\n"
            f"- 자치구: **{current['gu']}**\n\n"
            f"- 계획 세대수: **{int(current['households']) if pd.notna(current['households']) else '미상'} 세대**\n\n"
            f"- 정비구역면적: **{int(current['land_area_m2']):,} m²**"
        )
    color_controls_slot = st.container()
    legend_slot = st.empty()

with color_controls_slot:
    color_mode_key = f"color_mode_daily__{selected_gu}"
    default_idx = 0 if st.session_state.get("color_mode_daily_val","절대(30/70)").startswith("절대") else 1
    _ = st.radio("지도 색 기준", ["절대(30/70)","상대(30%/70%)"], index=default_idx, horizontal=True, key=color_mode_key,
                 help="절대: 혼잡도 30/70 고정 경계 · 상대: 분포의 30/70 분위수")
st.session_state["color_mode_daily_val"] = st.session_state.get(color_mode_key, "절대(30/70)")
legend_slot.caption("🟩 <30 · 🟨 30~70 · 🟥 ≥70 (단위: %) — 절대 기준 / 상대 선택 시: 분위 30/70 기준")

# ────────────────────────────────────────────────────────────────
# 3–4 사분면 레이아웃
# ────────────────────────────────────────────────────────────────
colL, colR = st.columns([1, 1], gap="large")

# 3-1: 주변 도로 혼잡도 (기준년도)
with colL:
    st.markdown("### 🚦 [3-1사분면] · 주변 도로 혼잡도 (기준년도)")

    with st.spinner("교통 기준년도 데이터 준비 중..."):
        load_speed_csv_from_xlsx_if_needed()
        if not TRAFFIC_CSV_PATH.exists():
            st.warning(
                f"기준 CSV가 없습니다: {TRAFFIC_CSV_PATH.name}\n"
                f"→ data 폴더에 {TRAFFIC_XLSX_PATH.name} 를 넣으면 자동 변환됩니다."
            )

    radius = st.slider("반경(m)", 500, 3000, 1000, step=250, key="radius_m")
    graph_topn = st.slider("그래프에 표시할 링크 수 (Top-N)", 5, 50, 10, 1, key="graph_topn")

    df_plot_all = None
    if TRAFFIC_CSV_PATH.exists() and SHP_PATH.exists():
        if _HAS_PLOT_SPEED:
            chart_speed, df_speed = plot_speed(
                csv_path=str(TRAFFIC_CSV_PATH),
                shp_path=str(SHP_PATH),
                center_lon=sel_lon, center_lat=sel_lat,
                radius_m=radius, max_links=graph_topn,
                renderer="altair", chart_height=300,
            )
            st.altair_chart(chart_speed, use_container_width=True, theme=None)

            # 지도/혼잡도용 전체 링크
            _, df_plot_all = plot_speed(
                csv_path=str(TRAFFIC_CSV_PATH),
                shp_path=str(SHP_PATH),
                center_lon=sel_lon, center_lat=sel_lat,
                radius_m=radius, max_links=10000,
                renderer="altair", chart_height=1,
            )
        else:
            _, df_plot_all = plot_speed_fallback(
                csv_path=str(TRAFFIC_CSV_PATH),
                shp_path=str(SHP_PATH),
                center_lon=sel_lon, center_lat=sel_lat,
                radius_m=radius, max_links=10000,
            )
    else:
        st.info("교통 CSV 또는 SHP가 없어 그래프/지도 데이터를 만들 수 없습니다.")

    # 혼잡도 및 GeoJSON 캐시 키 생성
    if (df_plot_all is not None) and (not df_plot_all.empty):
        df_metric_all = compute_congestion_from_speed(df_plot_all)
        st.session_state["df_plot_all"] = df_plot_all  # 3-2, 3-3에서 재사용

        df_daily = (
            df_metric_all.groupby("link_id", as_index=False)["value"].mean()
            .rename(columns={"value":"daily_value"})
        )

        color_mode = st.session_state.get("color_mode_daily_val", "절대(30/70)")
        if not df_daily.empty:
            key = build_daily_geojson_key(df_daily, color_mode)
            st.session_state["matched_geo_key_daily"] = key if key else None
        else:
            st.session_state["matched_geo_key_daily"] = None

            legend_text = ("🟩 <30 · 🟨 30~70 · 🟥 ≥70 (단위: %)"
                           if color_mode.startswith("절대")
                           else "🟩 <30% 분위 · 🟨 30~70% · 🟥 ≥70% 분위")
            legend_slot.caption(legend_text)


        render_map(view_state)

# 3-2: 혼잡지표(혼잡도) — Top-N 시간대 변화
with colL:
    st.markdown("### 📈 [3-2사분면] · 혼잡지표 (혼잡도)")
    df_plot_all = st.session_state.get("df_plot_all", None)
    graph_topn = st.session_state.get("graph_topn", 10)

    if (df_plot_all is not None) and (not df_plot_all.empty):
        df_metric_all = compute_congestion_from_speed(df_plot_all)
        rank = (
            df_metric_all.groupby("link_id", as_index=False)["value"].mean()
            .sort_values("value", ascending=False).head(graph_topn)
        )
        keep = set(rank["link_id"].astype(str))
        df_metric_chart = df_metric_all[df_metric_all["link_id"].astype(str).isin(keep)].copy()
        chart = (
            alt.Chart(df_metric_chart).mark_line(point=True)
            .encode(
                x=alt.X("hour:Q", title="시간대 (시)"),
                y=alt.Y("value:Q", title="혼잡도(%)", scale=alt.Scale(domain=[0, 100])),
                color=alt.Color("link_id:N", title="링크 ID",
                                legend=alt.Legend(orient="bottom", direction="horizontal", columns=4)),
                tooltip=[alt.Tooltip("link_id:N", title="링크"),
                         alt.Tooltip("hour:Q", title="시"),
                         alt.Tooltip("value:Q", title="혼잡도(%)", format=".1f")],
            ).properties(title=f"[3-2] 혼잡도 변화 — Top {graph_topn}", height=360)
            .configure_view(strokeWidth=0)
        )
        st.altair_chart(chart, use_container_width=True, theme=None)
        with st.expander("🧮 혼잡도(%) 정의", expanded=False):
            st.markdown("- 링크 $(l)$, 시간대 $(h)$의 평균속도 $v_{l,h}$, 자유주행속도 $v_{\\mathrm{ff},l}=\\max_h v_{l,h}$ 일 때")
            st.latex(r"\mathrm{혼잡도}_{l,h}(\%)=\Big(1-\min\big(1,\frac{v_{l,h}}{v_{\mathrm{ff},l}}\big)\Big)\times 100")
            st.markdown("- 값의 의미: **0% = 자유주행**, **100% = 매우 혼잡**")
    else:
        st.info("혼잡도 데이터를 계산할 수 없습니다.")

# 3-3: 추세 vs 재건축 후(추정)
with colL:
    st.markdown("### 📉 [3-3사분면] · 주변링크 추세(기준) vs 재건축 후(추정)")
    df_plot_all = st.session_state.get("df_plot_all", None)

    if (df_plot_all is None) or df_plot_all.empty:
        st.info("반경 내 링크 데이터가 없어 추세를 계산할 수 없습니다. [3-1]에서 반경을 조정해보세요.")
    else:
        def _congestionize(df):
            d = df.copy()
            d["평균속도(km/h)"] = pd.to_numeric(d["평균속도(km/h)"], errors="coerce")
            d["free_flow"] = d.groupby("link_id")["평균속도(km/h)"].transform("max").clip(lower=1)
            d["혼잡도(%)"] = ((1 - (d["평균속도(km/h)"] / d["free_flow"]).clip(0, 1)) * 100).clip(0, 100)
            return d[["link_id","hour","혼잡도(%)"]]

        d0 = _congestionize(df_plot_all)
        grp = d0.groupby("hour")["혼잡도(%)"]
        trend_base = (
            grp.mean().rename("mean").to_frame()
            .assign(p25=grp.quantile(0.25), p75=grp.quantile(0.75))
            .reset_index()
        )
        # 다항 회귀(최대 3차)
        x = trend_base["hour"].to_numpy().astype(float)
        y = trend_base["mean"].to_numpy().astype(float)
        deg = int(min(3, max(1, np.unique(x).size - 1)))
        coeff = np.polyfit(x, y, deg=deg)
        poly  = np.poly1d(coeff)
        trend_base["mean_fit"] = np.clip(poly(x), 0, 100)

        planned_hh = int(current.get("households") or 1000)
        # η 기본값(세션 우선)
        eta_default = st.session_state["eta_by_gu"].get(selected_gu, SENS_DEFAULTS.get(selected_gu, 0.60))

        c1, c2, c3 = st.columns([1.0, 1.0, 1.0])
        with c1:
            default_base_hh = int(np.clip(planned_hh * 0.8, 50, 30000))
            base_hh = int(st.number_input("기존 세대수(입력)", min_value=50, max_value=30000,
                                          value=default_base_hh, step=50,
                                          key=f"base_hh_{selected_gu}_{selected_row}"))
        with c2:
            st.number_input("계획 세대수(표)", value=planned_hh, disabled=True,
                            key=f"planned_hh_{selected_gu}_{selected_row}")
        sens = float(st.session_state.get("eta_by_gu", {}).get(selected_gu, eta_default))
        with c3:
            st.metric("민감도 η(구)", f"{sens:.2f}")






        # 기존 함수에 eps 인자 추가(슬라이더 의존 제거)
        def _hourly_weight_default(alpha_: float = 1.5, eps_: float = 0.05) -> np.ndarray:
            base = np.array([0.05, 0.05, 0.05, 0.05, 0.06, 0.12, 0.35, 0.60, 0.80, 0.70, 0.55, 0.50,
                             0.45, 0.45, 0.50, 0.65, 0.85, 1.00, 0.80, 0.55, 0.35, 0.20, 0.10, 0.07])
            w = (base / base.max()) ** float(alpha_)
            return np.maximum(w, float(eps_))


        # w(h) 제거 + 새벽만 아주 소폭 감쇠
        #   - min_factor=0.95  → 새벽 시간대에도 5%만 감소
        #   - turn_hour=6.5    → 06:30 전후를 중심으로 원래값(=1)로 회복
        #   - k=1.6            → 전이 구간을 짧게(급격히) 만들어 영향 최소화
        w_hour = np.ones(24, dtype=float)
        w_hour = apply_dawn_smoothing(w_hour, min_factor=0.2, turn_hour=6.5, k=1.6)


        with st.expander("시간대 가중치 w(h) 안내", expanded=False):
            st.markdown(f"- 전역 고정값 사용: α={ALPHA_HOURLY}, ε={EPS_HOURLY} · 새벽 완급 적용")

        # 재건축 후 혼잡 추정식
        r = (planned_hh / max(1.0, float(base_hh)))
        base = trend_base["mean_fit"].to_numpy()
        # 교체본 (w(h) 반영)
        w_series = pd.Series(w_hour, index=np.arange(24))  # 시간대→가중치 매핑
        w_for_hour = trend_base["hour"].astype(int).map(w_series).to_numpy()

        # w(h) → hour별로 매핑해서 반영


        after = 100.0 * (
                1.0 -
                (1.0 - base / 100.0) / (1.0 + sens * w_for_hour * (r - 1.0))
        )
        trend_base["after_fit"] = np.clip(after, 0, 100)

        # 시각화
        plot_df = trend_base[["hour", "mean_fit", "after_fit"]].melt(id_vars=["hour"], var_name="series",
                                                                     value_name="value")
        label_map = {"mean_fit":"기준 추세", "after_fit":"재건축 후(추정)"}
        plot_df["series"] = plot_df["series"].map(label_map)
        color_domain = ["기준 추세","재건축 후(추정)"]; color_range = ["#22c55e","#ef4444"]

        band = alt.Chart(trend_base).mark_area(opacity=0.18).encode(
            x=alt.X("hour:Q", title="시간대 (시)"),
            y=alt.Y("p25:Q", title="혼잡도(%)"),
            y2="p75:Q",
        )
        lines = alt.Chart(plot_df).mark_line(point=True).encode(
            x=alt.X("hour:Q", title="시간대 (시)"),
            y=alt.Y("value:Q", title="혼잡도(%)", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("series:N", title="", scale=alt.Scale(domain=color_domain, range=color_range)),
            tooltip=[alt.Tooltip("hour:Q", title="시"), alt.Tooltip("series:N", title=""), alt.Tooltip("value:Q", title="혼잡도(%)", format=".1f")],
        )
        chart_33 = (band + lines).properties(
            title=f"주변링크 혼잡 추세(기준) vs 재건축 후(추정) · r={r:.2f}, η={sens:.2f}", height=360
        ).configure_view(strokeWidth=0).configure_legend(orient="right")
        st.altair_chart(chart_33, use_container_width=True, theme=None)

        # >>> PATCH A: save curves for quadrant-4 needs ------------------------
        # >>> PATCH A2: 3-4 간소화용 자동기본값 계산/저장 -------------------
        try:
            # ① 기준 혼잡도(%) 기본값: base 곡선의 평균
            auto_cong = float(curve_33["base"].mean())

            # ② '기준 이하'로 만들기 위한 최소 증편률(%)
            auto_bus = compute_min_bus_increase_to_cap(
                after=curve_33["after"].to_numpy(),
                base=curve_33["base"].to_numpy()
            )

            # ③ 세대수/평형 기본
            auto_house = int(planned_hh)
            auto_py = float(st.session_state.get("desired_py", 25.0))

            # ④ 재무 공통(세션에 있으면 우선)
            auto_non_sale = float(st.session_state.get("non_sale_ratio", 0.15))
            auto_sale_rate = float(st.session_state.get("sale_rate", 0.98))
            auto_disc = float(st.session_state.get("disc_rate", 0.07))
            auto_years = int(st.session_state.get("years", 4))

            st.session_state["auto_defaults"] = {
                "congestion_base": auto_cong,
                "bus_inc_pct": float(np.clip(auto_bus, 0.0, 100.0)),
                "households": auto_house,
                "avg_py": auto_py,
                "non_sale_ratio": auto_non_sale,
                "sale_rate": auto_sale_rate,
                "disc_rate": auto_disc,
                "years": auto_years,
            }
        except Exception as _e:
            # 안전장치: 없으면 기본값 셋
            st.session_state["auto_defaults"] = st.session_state.get("auto_defaults", {
                "congestion_base": 50.0, "bus_inc_pct": 10.0,
                "households": int(current.get("households") or 1000),
                "avg_py": float(st.session_state.get("desired_py", 25.0)),
                "non_sale_ratio": 0.15, "sale_rate": 0.98, "disc_rate": 0.07, "years": 4
            })
        # -------------------------------------------------------------------

        curve_33 = trend_base[["hour", "mean_fit", "after_fit"]].rename(
            columns={"mean_fit": "base", "after_fit": "after"}
        ).copy()
        st.session_state["curve_33"] = curve_33
        # ---------------------------------------------------------------------

        # (대체할)기존코드 <- 주석처리
        # with st.expander("그래프/모형 설명 보기"):
        #     st.markdown("### 📘 무엇을 보나요?")
        #     st.markdown(
        #         "- **연한 영역**: 반경 내 모든 링크의 혼잡도 분위수 밴드(25–75%)\n"
        #         "- **기준 추세 (초록)**: 시간대별 평균 혼잡도를 3차 이하 다항으로 근사\n"
        #         "- **재건축 후 (빨강)**: 세대 증가 비율 `r = (계획/기존)`과 민감도 `η`를 반영한 간이 추정"
        #     )
        #     st.markdown("### ⚙️ 추정식")
        #     st.latex(
        #         r"""
        #         \text{after}(h)= 100 \times
        #         \left[
        #             1 -
        #             \frac{
        #                 1 - \dfrac{\text{base}(h)}{100}
        #             }{
        #                 1 + \eta\,(r - 1)
        #             }
        #         \right]
        #         """
        #     )
        #     st.markdown("### 🔣 기호 설명")
        #     st.latex(r"\text{base}(h):\; \text{기준 추세 혼잡도(\%)}")
        #     st.latex(r"r:\; \dfrac{\text{계획세대수}}{\text{기존세대수}}")
        #     st.latex(r"\eta:\; \text{구별 민감도 (혼잡 탄력성)}")

        # (수정된) 새로운 설명 블록 — w(h)·α·ε 반영
        with st.expander("그래프/모형 설명 보기"):
            st.markdown("### 📘 무엇을 보나요?")
            st.markdown(
                "- **연한 영역**: 반경 내 모든 링크의 혼잡도 분위수 밴드(25–75%)\n"
                "- **기준 추세 (초록)**: 시간대별 평균 혼잡도를 3차 이하 다항으로 근사한 곡선\n"
                "- **재건축 후 (빨강)**: 세대 증가 비율 `r = (계획/기존)`과 **민감도 `η`에 시간대 가중치 `w(h)`**를 곱해 반영한 간이 추정"
            )
            st.markdown("### ⚙️ 추정식 (시간대 가중 반영)")
            st.latex(
                r"""
                \text{after}(h)= 100 \times 
                \left[
                    1 -
                    \frac{1 - \dfrac{\text{base}(h)}{100}}
                         {1 + \eta\,\underbrace{\tilde{w}(h)}_{\approx\,1,\ \text{dawn}\simeq0.95}\,(r - 1)}
                \right]


                """
            )
            st.markdown("### 🔣 기호 설명")
            st.latex(r"\text{base}(h):\; \text{기준 추세 혼잡도(\%)}")
            st.latex(r"r:\; \dfrac{\text{계획세대수}}{\text{기존세대수}}")
            st.latex(r"\eta:\; \text{구별 민감도 (혼잡 탄력성)}")
            st.latex(r"w(h):\; \text{시간대 가중치, 심야}\approx 0,\; \text{피크}\approx 1")
            st.markdown(
                "- `w(h)`는 반경 내 시간대별 총 차량대를 정규화해 만들고, "
                "`α`(피크 강조) 지수와 `ε`(심야 최소 영향) 하한을 적용합니다.\n"
                "  - `α`↑ → 피크 영향 확대, 심야 영향 축소\n"
                "  - `ε`는 0으로 두면 곡선이 급격히 꺾일 수 있어, 기본적으로 소량(예: 0.05) 부여"
            )


# 3-4: 시나리오/민감도/확률
def calc_kpis(
    households:int, avg_py:float, sale_price_per_m2:float, build_cost_per_m2:float, infra_invest_billion:float,
    congestion_base:float, bus_inc_pct:int, non_sale_ratio:float=0.15, sale_rate:float=0.98, disc_rate:float=0.07, years:int=4
):
    m2_per_py = 3.3058
    avg_m2 = avg_py * m2_per_py
    sellable_m2 = households * avg_m2 * (1 - non_sale_ratio)
    predicted_cong = max(0.0, congestion_base * (1 - bus_inc_pct / 150))
    cong_improve = max(0.0, congestion_base - predicted_cong)

    revenue_won = sellable_m2 * sale_price_per_m2 * sale_rate
    cost_won = sellable_m2 * build_cost_per_m2
    total_cost_bil = cost_won/1e4/100 + infra_invest_billion
    total_rev_bil  = revenue_won/1e4/100

    profit_bil = total_rev_bil - total_cost_bil
    margin_pct = (profit_bil / total_cost_bil * 100) if total_cost_bil>0 else 0

    cf_annual = profit_bil / years if years>0 else profit_bil
    npv = sum([cf_annual / ((1+disc_rate)**t) for t in range(1, years+1)]) if years>0 else profit_bil
    payback = min(years, max(1, int(np.ceil(total_cost_bil / max(1e-6, cf_annual))))) if years>0 else 1

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

    # 3-4: 시나리오/민감도/확률  ← 기존 내용 전부 삭제하고 아래로 교체
    with colL:
        st.markdown("### 🧾 [3-4사분면] · 시나리오 & 재무/민감도 & 확률")
        # 제목만 남기고 빈 공간 확보 (필요시 높이 조절)
        st.markdown("<div style='height: 260px'></div>", unsafe_allow_html=True)

    # -------------------------------------------------------------------



# 4사분면: 최종 리포트
# 4사분면: 최종 리포트  ← 기존 내용 전부 삭제하고 아래로 교체
with colR:
    st.markdown("### 🧩 [4사분면] · 최종 리포트 & 분석")
    # 제목만 남기고 넉넉한 빈 공간
    with st.container(border=True):
        st.caption("이 영역은 현재 비워둠")
        st.markdown("<div style='height: 520px'></div>", unsafe_allow_html=True)

        # ---------------------------------------------------------------------

# ----------------------------------------------------
# 🧾 확장 섹션: 시나리오 & 재무/민감도 & 확률 (하단 분리)
# ----------------------------------------------------
st.divider()
with st.expander("🧾 [확장] 시나리오 & 재무/민감도 & 확률", expanded=False):

    st.markdown("### 🧾 [3-4사분면] · 시나리오 & 재무/민감도 & 확률")
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
            a,b,c,d = st.columns(4, gap="small")
            with a: sale = st.number_input(f"{label}·분양가(만원/㎡)", 500.0, 3000.0, sale_default, 10.0, key=f"sale_{label}")
            with b: cost = st.number_input(f"{label}·공사비(만원/㎡)", 300.0, 2500.0, cost_default, 10.0, key=f"cost_{label}")
            with c: bus = st.slider(f"{label}·버스증편(%)", 0, 100, bus_default, 5, key=f"bus_{label}")
            with d: infra = st.number_input(f"{label}·인프라(억원)", 0.0, 1000.0, infra_default, 5.0, key=f"infra_{label}")
            return sale, cost, bus, infra

        saleA, costA, busA, infraA = scenario_inputs("A", 1200.0, 900.0, base_bus_inc, 30.0)
        saleB, costB, busB, infraB = scenario_inputs("B", 1300.0, 950.0, base_bus_inc+10, 50.0)
        saleC, costC, busC, infraC = scenario_inputs("C", 1100.0, 850.0, max(0, base_bus_inc-5), 20.0)

        scenarios = {"A": dict(sale=saleA, cost=costA, bus=busA, infra=infraA),
                     "B": dict(sale=saleB, cost=costB, bus=busB, infra=infraB),
                     "C": dict(sale=saleC, cost=costC, bus=busC, infra=infraC)}

        rows = []
        for name, s in scenarios.items():
            k = calc_kpis(households, avg_py, s["sale"], s["cost"], s["infra"], congestion_base, s["bus"],
                          non_sale_ratio, sale_rate, disc_rate, years)
            rows.append({"시나리오": name, **k})
        df_scn = pd.DataFrame(rows).set_index("시나리오")
        st.markdown("#### 📊 시나리오 비교표")
        st.dataframe(df_scn, use_container_width=True)
        best = df_scn.sort_values("NPV(억원)", ascending=False).head(1)
        st.success(f"**추천 시나리오: {best.index[0]}** · NPV {best['NPV(억원)'].iloc[0]:,.1f}억원 · 마진율 {best['마진율(%)'].iloc[0]:.1f}%")

        st.session_state["df_scn_result"] = df_scn
        st.session_state["df_scn_summary_for_charts"] = df_scn.reset_index()[["시나리오","NPV(억원)","마진율(%)","혼잡도개선(Δ%)"]]

    with tab2:
        st.markdown("#### 📈 민감도 분석 (토네이도)")
        base_sale = st.number_input("기준 분양가(만원/㎡)", 500.0, 3000.0, 1200.0, 10.0)
        base_cost = st.number_input("기준 공사비(만원/㎡)", 300.0, 2500.0, 900.0, 10.0)
        base_bus  = st.slider("기준 버스증편(%)", 0, 100, 20, 5)
        base_infra= st.number_input("기준 인프라(억원)", 0.0, 1000.0, 30.0, 5.0)
        pct = st.slider("변동폭(±%)", 1, 30, 15, 1)

        def kpi_with(sale, cost, bus, infra):
            return calc_kpis(households, avg_py, sale, cost, infra, congestion_base, bus,
                             non_sale_ratio, sale_rate, disc_rate, years)["NPV(억원)"]

        base_npv = kpi_with(base_sale, base_cost, base_bus, base_infra)
        factors = []
        ranges = {
            "분양가": (base_sale*(1-pct/100), base_sale*(1+pct/100)),
            "공사비": (base_cost*(1-pct/100), base_cost*(1+pct/100)),
            "버스증편": (max(0, base_bus-pct), min(100, base_bus+pct)),
            "인프라": (max(0, base_infra*(1-pct/100)), base_infra*(1+pct/100)),
        }
        for name, (lo, hi) in ranges.items():
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
        ).properties(height=220)
        st.altair_chart(bars, use_container_width=True)
        st.session_state["df_tornado"] = df_tornado
        st.session_state["base_npv_for_tornado"] = float(base_npv)

    with tab3:
        st.markdown("#### 🎲 확률 분석 (간이 Monte Carlo)")
        n = st.slider("시뮬레이션 반복수", 200, 5000, 1000, 100)
        sigma_sale = st.slider("분양가 표준편차(%)", 1, 20, 7)
        sigma_cost = st.slider("공사비 표준편차(%)", 1, 20, 5)
        rng = np.random.default_rng(42)
        sale_samples = rng.normal(loc=base_sale, scale=base_sale*sigma_sale/100, size=n)
        cost_samples = rng.normal(loc=base_cost, scale=base_cost*sigma_cost/100, size=n)
        def kpi_with_sale_cost(s, c):
            return calc_kpis(households, avg_py, s, c, base_infra, congestion_base, base_bus,
                             non_sale_ratio, sale_rate, disc_rate, years)["NPV(억원)"]
        npvs = [kpi_with_sale_cost(max(100, s), max(100, c)) for s, c in zip(sale_samples, cost_samples)]
        ser = pd.Series(npvs)
        p10, p50, p90 = np.percentile(ser, [10, 50, 90])
        st.metric("P10 NPV", f"{p10:,.1f} 억원")
        st.metric("P50 NPV", f"{p50:,.1f} 억원")
        st.metric("P90 NPV", f"{p90:,.1f} 억원")
        st.caption("※ P10: 보수적(하위 10%), P90: 낙관적(상위 10%)")
        hist = alt.Chart(pd.DataFrame({"NPV": ser})).mark_bar().encode(
            x=alt.X("NPV:Q", bin=alt.Bin(maxbins=30), title="NPV(억원)"),
            y="count()"
        ).properties(height=200)
        st.altair_chart(hist, use_container_width=True)
        st.session_state["mc_p10p50p90"] = (float(p10), float(p50), float(p90))
        st.session_state["mc_samples_npv"] = ser.tolist()

    with tab4:
        st.info("📌 오른쪽 **[4사분면] 최종 리포트** 패널에서 종합 요약·자동 해석·내보내기를 확인하세요. (안내용)")


# 초기 지도 렌더(데이터 계산 전에 호출된 경우 대비)
render_map(view_state)
