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
import pandas as pd
import numpy as np
import pydeck as pdk
import altair as alt
from datetime import datetime

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



#===========================캐시 비우기=================


with st.sidebar:
    if st.button("캐시 비우기"):
        st.cache_data.clear()
        st.rerun()
   # 즉시 재실행
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
# 변경:
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

    p_cong(V) = 1 / (1 + exp((V - vb) / tau)),  vb는 경계속도
    혼잡빈도강도(%) = 100 * ( sum(volume * p_cong) / sum(volume) )

    - hour 정규화: 0~23
    - 속도/교통량 숫자형 강제 변환
    """
    # --- 속도 데이터 정리 ---
    d = speed_df.copy()
    d["link_id"] = d["link_id"].astype(str)
    d["hour"] = pd.to_numeric(d["hour"], errors="coerce").astype("Int64")  # allow NA
    d["평균속도(km/h)"] = pd.to_numeric(d["평균속도(km/h)"], errors="coerce")

    # --- 교통량 데이터 정리 ---
    v = vol_df.copy()
    v["link_id"] = v["link_id"].astype(str)
    # "0시" 같은 문자열이 와도 안전하게 0~23으로 정규화
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
    # V > vb이면 0쪽, V < vb이면 1쪽으로 연속적으로 변함
    m["p_cong"] = 1.0 / (1.0 + np.exp((m["평균속도(km/h)"] - vb) / tau))

    # --- 링크×시간대로 집계 (교통량 가중 평균) ---
    # 가중평균: sum(w*x)/sum(w)
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
/* Streamlit의 기본 center 정렬을 강제로 무력화 — 더 강한 선택자 사용 */
div[data-testid="stMarkdownContainer"] .katex-display {
    text-align: left !important;
    margin-left: 0 !important;
    margin-right: auto !important;
}

/* KaTeX 내부 박스를 줄 맞춰 붙게 */
div[data-testid="stMarkdownContainer"] .katex-display > .katex {
    display: inline-block !important;
}

/* 일반 문단도 혹시 모를 가운데정렬을 방지 */
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
        # 숫자만 추출(지상/지하 둘 다 안전하게 처리)
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
        "far": _pct_to_num(get("용적률")),          # 용적률(%) → 숫자
        "floors": _floors_to_num(get("층수")),      # 단일 ‘층수’가 있을 때
        "status": get("진행단계"),                  # ✅ 진행단계 추가
        # ⬇️ 지상/지하층수 지원 (있으면 표시용으로 예쁘게)
        "floors_up": _floors_to_num(get("지상층수")),
        "floors_down": _floors_to_num(get("지하층수")),
    })

    # 층수 표시 문자열 (예: "지상 35 / 지하 3")
    def _fmt_floor(u, d):
        parts = []
        if pd.notna(u):
            parts.append(f"지상 {int(u)}")
        if pd.notna(d):
            parts.append(f"지하 {int(d)}")
        return " / ".join(parts)

    df["floors_display"] = [_fmt_floor(u, d) for u, d in zip(df["floors_up"], df["floors_down"])]

    # 최종 표시용 층수: 지상/지하가 있으면 그걸 쓰고, 없으면 단일 숫자층을 "N층"으로
    df["floors_show"] = df["floors_display"].fillna("").astype(str).str.strip()
    mask_empty = df["floors_show"] == ""
    df.loc[mask_empty, "floors_show"] = df.loc[mask_empty, "floors"].apply(
        lambda x: f"{int(x)}층" if pd.notna(x) else ""
    )

    # 문자열 정리
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
# - 첫 진입: selected_row 키가 없으니 None으로 세팅
# - 자치구를 변경했을 때: 이전 구와 다르면 선택을 리셋
if "selected_row" not in st.session_state:
    st.session_state.selected_row = None
if "selected_gu_prev" not in st.session_state:
    st.session_state.selected_gu_prev = selected_gu

if st.session_state.selected_gu_prev != selected_gu:
    st.session_state.selected_row = None           # 구가 바뀌면 선택 초기화
    st.session_state.selected_gu_prev = selected_gu

st.sidebar.markdown(
    "<div class='small-muted'>구 선택 시, 해당 구의 정비사업 단지 목록과 지도가 갱신됩니다.</div>",
    unsafe_allow_html=True,
)

project_name = st.sidebar.text_input("프로젝트 이름", value=f"{selected_gu} 재건축 시나리오")

# -------------------------------------------------------------
# 🗺️ 1-2사분면: 지도 + 단지 선택
# -------------------------------------------------------------
col12_left, col12_right = st.columns([2.2, 1.4], gap="large")

with col12_left:
    st.markdown("### 🗺 1-2사분면 · 지도 & 단지선택")

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
    # 1) 원본 CSV 그대로 보기
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

    # 2) 현재 화면에 쓰는 df_map 값 보기
    st.caption("현재 표시값(df_map)")
    st.dataframe(
        df_map[["gu", "address_display", "name", "households", "land_area_m2"]].head(20),
        use_container_width=True
    )

    # 3) 원본값과 df_map 값 자동 비교 (name+gu 기준)
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

    # 정수/실수 비교: 면적은 부동소수점 오차를 허용
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

# ✅ 테이블에 쓸 컬럼 구성
# ✅ 테이블에 쓸 컬럼 구성 (용적률/층수/진행단계 포함)
df_list = df_map[[
    "apt_id",
    "address_display",
    "org_name", "biz_type", "op_type",
    "status",            # 진행단계
    "households", "land_area_m2",
    "far",               # 용적률(%)
    "floors_show",       # 층수(지상/지하 있으면 예쁘게, 없으면 N층)
]].copy()

# 숫자형 보정 (표시형 텍스트인 floors_show는 그대로)
df_list["households"]   = pd.to_numeric(df_list["households"], errors="coerce")
df_list["land_area_m2"] = pd.to_numeric(df_list["land_area_m2"], errors="coerce")
df_list["far"]          = pd.to_numeric(df_list["far"], errors="coerce")

# ===== 필터 영역 =====
fcol1, fcol2, fcol3, fcol4 = st.columns([1.6, 1.4, 1.6, 1.2])

with fcol1:
    kw = st.text_input("검색어(주소/조합명/키워드)", value="", placeholder="예) 개포, 목동, 조합")

# ✅ 드롭다운 범주 정의
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


# ===== 필터 적용 =====
mask = pd.Series(True, index=df_list.index)

if kw.strip():
    _kw = kw.strip().lower()
    mask &= (
        df_list["address_display"].fillna("").str.lower().str.contains(_kw) |
        df_list["org_name"].fillna("").str.lower().str.contains(_kw)
    )

# ✅ 드롭다운 선택값을 실제 필터로 적용
hh_lo, hh_hi = HH_BUCKETS[hh_choice]
la_lo, la_hi = AREA_BUCKETS[la_choice]

# 세대수 필터
col_series = df_list["households"].fillna(-1)
if hh_lo is not None:
    mask &= col_series >= hh_lo
if hh_hi is not None:
    mask &= col_series <= hh_hi

# 면적 필터
col_series = df_list["land_area_m2"].fillna(-1)
if la_lo is not None:
    mask &= col_series >= la_lo
if la_hi is not None:
    mask &= col_series <= la_hi

# 0/결측치 숨기기
if hide_zero:
    mask &= df_list["households"].fillna(0) > 0
    mask &= df_list["land_area_m2"].fillna(0) > 0

filtered = df_list[mask].reset_index().rename(columns={"index": "orig_index"})

# ===== 정렬 옵션 =====
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

# ===== 테이블 표시 (요청한 컬럼/라벨로)
show_df = filtered[[
    "orig_index",
    "address_display", "org_name", "biz_type", "op_type",
    "status",                    # 진행단계
    "households", "land_area_m2",
    "far", "floors_show",        # 용적률, 층수
]].copy().rename(columns={
    "address_display": "주소",
    "org_name": "추진위원회/조합명",
    "biz_type": "사업구분",
    "op_type": "운영구분",
    "status": "진행단계",
    "households": "계획세대수",
    "land_area_m2": "면적",
    "far": "용적률(%)",
    "floors_show": "층수",        # 표시용 텍스트를 ‘층수’ 라벨로
})

# ✅ 표 내부에서 직접 선택하는 '선택' 컬럼 추가(단일 선택 강제 로직은 기존 그대로 유지)
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
        "진행단계", "계획세대수", "면적", "용적률(%)", "층수"   # 비편집
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
        "층수": st.column_config.TextColumn("층수"),  # 지상/지하 표기가 들어갈 수 있어 TextColumn
    },
    key=f"project_table_{selected_gu}",
)

# ✅ 단일 선택 강제 로직
prev = st.session_state.selected_row
sel_list = [int(x) for x in edited.loc[edited["선택"] == True, "orig_index"].tolist()]

if len(sel_list) == 0:
    # 체크를 모두 해제한 경우: 이전 선택이 목록에 있으면 유지, 없으면 첫 행으로
    if prev in curr_ids:
        st.session_state.selected_row = int(prev)
    elif curr_ids:
        st.session_state.selected_row = int(curr_ids[0])
elif len(sel_list) == 1:
    st.session_state.selected_row = int(sel_list[0])
else:
    # 여러 개 체크된 경우 → 새로 체크된(이전 선택이 아닌) 첫 후보로 강제 전환
    if prev in sel_list:
        new_choice = next((x for x in sel_list if x != prev), sel_list[0])
    else:
        new_choice = sel_list[0]
    st.session_state.selected_row = int(new_choice)
    # 다음 렌더에서 한 개만 체크된 상태로 보이도록 즉시 재렌더
    st.rerun()

# 최종 선택값 확정
if st.session_state.selected_row is None:
    st.info("선택된 행이 없습니다.")
    st.stop()
selected_row = st.session_state.selected_row


# ✅ 지도 데이터/레이어 만들기 (selected_row 확정 이후)
filtered_indices = edited["orig_index"].tolist()
map_data = df_map.loc[filtered_indices].reset_index(drop=True)

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
    "html": "<b>{address_display}</b><br/>자치구: {gu}<br/>세대수: {households}<br/>구역면적(m²): {land_area_m2}",
    "style": {"backgroundColor": "#0f172a", "color": "white"},
}

if map_data.empty:
    st.info("조건에 맞는 단지가 없습니다. 필터를 조정해보세요.")
    map_slot.pydeck_chart(pdk.Deck(layers=[layer_highlight], initial_view_state=view_state, tooltip=tooltip))
else:
    map_slot.pydeck_chart(pdk.Deck(layers=[layer_points, layer_highlight], initial_view_state=view_state, tooltip=tooltip))


# --- 지도 렌더 (왼쪽 컬럼에서 실행) ---
with col12_left:
    if map_data.empty:
        st.info("조건에 맞는 단지가 없습니다. 필터를 조정해보세요.")
        map_slot.pydeck_chart(
            pdk.Deck(
                layers=[layer_highlight],

                initial_view_state=view_state,
                tooltip=tooltip,
            )
        )
    else:
        map_slot.pydeck_chart(
            pdk.Deck(
                layers=[layer_points, layer_highlight],
                initial_view_state=view_state,
                tooltip=tooltip,
            )
        )

with col12_right:
    st.markdown("### 🧾 1사분면 · 신설조건 입력")
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

    st.markdown("<hr class='soft'/>", unsafe_allow_html=True)
    desired_py = st.number_input("원하는 전용 평형(평)", min_value=15, max_value=60, value=34, step=1)


    # --- 기존 코드 교체 ---
    # desired_households = st.number_input("원하는 세대수(신규)", min_value=100, max_value=3000,
    #                                      value=int(current["households"]) + 200 if pd.notna(current["households"]) else 500, step=50)

    def _clamp(v, lo, hi):
        return max(lo, min(hi, v))


    min_val, max_val = 100, 3000
    base_households = int(current["households"]) if pd.notna(current["households"]) else 500
    default_desired = base_households + 200

    desired_households = st.number_input(
        "원하는 세대수(신규)",
        min_value=min_val,
        max_value=max_val,
        value=_clamp(default_desired, min_val, max_val),
        step=50,
    )

    expected_pop_increase_ratio = st.slider("예상 인구증가율(%)", 0, 100, 15, 5)
    new_bus_count = st.slider("신설 버스 대수", 0, 20, 2, 1)
    bus_capacity = st.number_input("버스 1대 수용 인원(명)", min_value=30, max_value=120, value=70, step=5)



        # 그래프 렌더 생략
    # else: 이미 CSV가 있으므로 그대로 사용

# 3–4사분면 레이아웃 컬럼
col3, col4 = st.columns([1.6, 1.4], gap="large")


# === 3사분면: 혼잡도 그래프 ===

# 3사분면 섹션 시작 전에 CSV 보장
with st.spinner("교통 기준년도 데이터 준비 중..."):
    if TRAFFIC_XLSX_PATH.exists():
        ensure_speed_csv(TRAFFIC_XLSX_PATH, TRAFFIC_CSV_PATH)  # ✅ 이름 수정
    elif not TRAFFIC_CSV_PATH.exists():
        st.warning(f"기준 CSV가 없습니다: {TRAFFIC_CSV_PATH.name}\n"
                   f"→ data 폴더에 {TRAFFIC_XLSX_PATH.name} 를 넣으면 자동 변환됩니다.")



# ===
sel_lat = float(current.get("lat", 37.5667))
sel_lon = float(current.get("lon", 126.9784))

with col3:
    st.markdown("### 🚦 3사분면 · 주변 도로 혼잡도 (기준년도)")


    radius = st.slider("반경(m)", 500, 3000, 1000, step=250, key="radius_m")
    max_links = st.slider("표시 링크 수", 5, 20, 10, step=1, key="max_links")

    if TRAFFIC_CSV_PATH.exists() and SHP_PATH.exists():
        if _HAS_PLOT_SPEED:
            chart_or_fig, df_plot = plot_speed(
                csv_path=TRAFFIC_CSV_PATH,
                shp_path=SHP_PATH,
                center_lon=sel_lon,
                center_lat=sel_lat,
                radius_m=radius,
                max_links=max_links,
                renderer="altair",
                chart_height=700,
            )

            # Altair Chart이면 st.altair_chart()로 표시
            if isinstance(chart_or_fig, alt.Chart):
                # Streamlit 테마가 Altair config를 덮어쓰지 않게
                st.altair_chart(chart_or_fig, use_container_width=True, theme=None)
            else:
                st.pyplot(chart_or_fig, use_container_width=True)

        else:
            # utils에 plot_speed가 없거나 로딩 실패 시, 기존 함수로 안전하게 표시
            fig, df_plot = plot_nearby_speed_from_csv(
                csv_path=TRAFFIC_CSV_PATH,
                shp_path=SHP_PATH,
                center_lon=sel_lon,
                center_lat=sel_lat,
                radius_m=radius,
                max_links=max_links,
            )
            st.pyplot(fig, use_container_width=True)

        with st.expander("데이터 미리보기"):
            st.dataframe(
                df_plot.sort_values(["link_id", "hour"]).head(300),
                use_container_width=True
            )
    else:
        st.info("교통 CSV 또는 SHP가 없어 그래프를 생략합니다.")

# === 혼잡도 / 혼잡빈도강도 토글 그래프 ===
if df_plot is not None and not df_plot.empty:
    st.markdown("### 📈 혼잡지표 비교 (혼잡도 vs 혼잡빈도강도)")

    # --- 혼잡도 계산 ---
    def compute_congestion_from_speed(df_plot):
        d = df_plot.copy()
        # 🔹 속도 데이터를 숫자형으로 강제 변환
        d["평균속도(km/h)"] = pd.to_numeric(d["평균속도(km/h)"], errors="coerce")

        # 🔹 자유주행속도 계산 후 혼잡도 계산
        d["free_flow"] = d.groupby("link_id")["평균속도(km/h)"].transform("max").clip(lower=1)
        d["혼잡도(%)"] = ((1 - (d["평균속도(km/h)"] / d["free_flow"]).clip(0, 1)) * 100).clip(0, 100)
        d["지표명"] = "혼잡도"
        return d[["link_id", "hour", "혼잡도(%)", "지표명"]]


    # --- 혼잡빈도강도 계산 ---
    def compute_congestion_freq_intensity(df_plot, boundary_speed=30):
        d = df_plot.copy()
        d["평균속도(km/h)"] = pd.to_numeric(d["평균속도(km/h)"], errors="coerce")
        d["혼잡빈도강도(%)"] = (d["평균속도(km/h)"] <= boundary_speed).astype(int) * 100
        d = (
            d.groupby(["link_id", "hour"], as_index=False)["혼잡빈도강도(%)"]
            .mean()
        )
        d["지표명"] = "혼잡빈도강도"
        return d


    def compute_cfi_weighted_robust(
            speed_df: pd.DataFrame,
            vol_df: pd.DataFrame,
            boundary_mode: str = "percentile",  # "fixed" or "percentile"
            boundary_value: float = 30.0,  # fixed: km/h, percentile: 10~90
            min_samples: int = 1  # 시간대별 최소 표본 차량수
    ):
        """
        - hour 정렬 자동보정 (0~23 강제)
        - 혼잡경계속도 동적 산정 지원:
            * boundary_mode="fixed": boundary_value(km/h) 그대로 사용
            * boundary_mode="percentile": speed 분포의 p-분위수(km/h) 사용
        - 차량 표본이 너무 적은 시간대는 제외(또는 0 처리)
        """
        d = speed_df.copy()
        d["link_id"] = d["link_id"].astype(str)
        d["hour"] = pd.to_numeric(d["hour"], errors="coerce").astype("Int64")
        d["평균속도(km/h)"] = pd.to_numeric(d["평균속도(km/h)"], errors="coerce")

        v = vol_df.copy()
        v["link_id"] = v["link_id"].astype(str)
        v["hour"] = pd.to_numeric(v["hour"], errors="coerce").astype("Int64") % 24
        v["차량대수"] = pd.to_numeric(v["차량대수"], errors="coerce").fillna(0)

        # 병합
        m = d.merge(v, on=["link_id", "hour"], how="inner").dropna(subset=["평균속도(km/h)"])

        # boundary 결정
        if boundary_mode == "percentile":
            import numpy as np
            p = float(boundary_value)
            p = max(5.0, min(95.0, p))
            boundary = np.nanpercentile(m["평균속도(km/h)"], p)
        else:
            boundary = float(boundary_value)

        m["혼잡차량수"] = (m["평균속도(km/h)"] <= boundary).astype(int) * m["차량대수"]

        g = (m.groupby(["link_id", "hour"], as_index=False)
             .agg(전체차량수=("차량대수", "sum"),
                  혼잡차량수=("혼잡차량수", "sum")))

        g.loc[g["전체차량수"] < max(1, min_samples), ["혼잡차량수", "전체차량수"]] = np.nan
        g["혼잡빈도강도(%)"] = (g["혼잡차량수"] / g["전체차량수"]) * 100
        g["혼잡빈도강도(%)"] = g["혼잡빈도강도(%)"].fillna(0).clip(0, 100)

        g.attrs = {"boundary": boundary, "mode": boundary_mode}
        return g


    # --- 사용자 토글 ---
    metric_choice = st.radio(
        "표시할 혼잡지표 선택",
        ["혼잡도", "혼잡빈도강도"],
        horizontal=True,
        index=0,
        key="metric_toggle"
    )

    # ------------------------------
    # 혼잡도 / 혼잡빈도강도 계산
    # ------------------------------
    if metric_choice == "혼잡도":
        df_metric = compute_congestion_from_speed(df_plot).rename(columns={"혼잡도(%)": "value"})
        y_title = "혼잡도 (0=자유주행, 100=매우혼잡)"
    else:
        # 교통량 파일이 있으면 '교통량 가중 Soft CFI', 없으면 단순 CFI
        vol_path = DATA_DIR / "TrafficVolume_Seoul_2023.csv"
        if vol_path.exists():
            vol_norm = load_volume_csv(vol_path)

            # 경계속도/밴드 UI
            bcol1, bcol2, bcol3 = st.columns([1, 1, 1])
            with bcol1:
                boundary_mode = st.radio("경계방식", ["percentile", "fixed"], horizontal=True, index=0, key="bd_mode")
            with bcol2:
                if boundary_mode == "percentile":
                    boundary_value = float(st.slider("속도분포 분위수(%)", 10, 90, 40, 5, key="bd_pct"))
                else:
                    boundary_value = float(st.number_input("고정 경계속도(km/h)", 10.0, 100.0, 30.0, 1.0, key="bd_fix"))
            with bcol3:
                band_kmh = float(st.slider("완화 밴드폭 (km/h)", 5, 20, 10, 1, key="bd_band"))

            # 교통량 가중 Soft CFI
            df_cfi = compute_cfi_soft(
                df_plot, vol_norm,
                boundary_mode=boundary_mode,
                boundary_value=boundary_value,
                tau_kmh=band_kmh
            )

            used_boundary = getattr(df_cfi, "attrs", {}).get("boundary", None)
            if used_boundary is not None:
                st.caption(f"사용된 경계속도 ≈ {used_boundary:.1f} km/h (밴드폭 {band_kmh:.1f} km/h)")

            df_metric = df_cfi.rename(columns={"혼잡빈도강도(%)": "value"})
            y_title = "혼잡빈도강도 (교통량 가중 · Soft)"
        else:
            # 볼륨 파일 없을 때의 단순 CFI
            df_metric = compute_congestion_freq_intensity(df_plot).rename(columns={"혼잡빈도강도(%)": "value"})
            y_title = "혼잡빈도강도 (혼잡구간 차량비율)"

    # ------------------------------
    # ✅ 차트 그리기
    # ------------------------------
    # 평균속도 그래프와 비슷한 높이
    CHART_H = 400  # average speed에서 chart_height=700 이라면 동일 적용
    HALF_W = 1100  # 가로 절반 느낌의 고정폭(원하면 500~700에서 조정)

    chart = (
        alt.Chart(df_metric)
        .mark_line(point=True)
        .encode(
            x=alt.X("hour:Q", title="시간대 (시)"),
            y=alt.Y("value:Q", title=y_title, scale=alt.Scale(domain=[0, 100])),
            color=alt.Color(
                "link_id:N",
                title="링크 ID",
                legend=alt.Legend(
                    orient="bottom",  # ✅ 범주를 아래쪽에 배치
                    direction="horizontal",  # 가로로 나열
                    columns=4  # 한 줄에 4개씩 (원하면 3~6으로 조정 가능)
                ),
            ),
            tooltip=[
                alt.Tooltip("link_id:N", title="링크"),
                alt.Tooltip("hour:Q", title="시"),
                alt.Tooltip("value:Q", title=y_title, format=".1f"),
            ],
        )
        .properties(
            title=f"{metric_choice} 변화 추이",
            width=HALF_W,  # ⬅️ 가로폭 고정
            height=CHART_H  # ⬅️ 세로높이 고정(평균속도와 맞춤)
        )
        .configure_view(strokeWidth=0)
    )

    # width/height를 적용하려면 use_container_width=False 로!
    st.altair_chart(chart, use_container_width=False, theme=None)

    # ------------------------------
    # ✅ 그래프 아래 수식/설명
    # ------------------------------
    if metric_choice == "혼잡도":
        st.markdown("### 🧮 혼잡도(%) 정의")
        st.markdown("- 링크 $(l)$, 시간대 $(h)$에서의 평균속도를 $v_{l,h}$ 라 할 때,")
        st.latex(r"v_{\mathrm{ff},l}=\max v_{l,h}")
        st.latex(r"\mathrm{혼잡도}_{l,h}(\%)=\Big(1-\min\big(1,\frac{v_{l,h}}{v_{\mathrm{ff},l}}\big)\Big)\times 100")
        st.markdown("- 값의 의미: **0% = 자유주행**, **100% = 매우 혼잡**")
    else:
        st.markdown("### 🧮 혼잡빈도강도(%) 정의 (교통량 가중 · Soft)")
        st.markdown("- 경계속도 $v_b$ 부근에서 부드럽게 전환되는 시그모이드 확률로 혼잡 여부를 근사합니다.")
        st.latex(r"p_{\mathrm{cong}}(v)=\frac{1}{1+\exp\!\left(\frac{v-v_b}{\tau}\right)}")
        st.markdown("- 링크·시간대별 혼잡빈도강도는 **교통량 가중 평균**으로 계산합니다.")
        st.latex(r"""\mathrm{CFI}_{l,h}(\%)=100\times
        \frac{\sum_i w_{l,h,i}\,p_{\mathrm{cong}}(v_{l,h,i})}{\sum_i w_{l,h,i}}""")
        st.markdown("- 여기서 $w$는 차량대수, $\\tau$는 전환의 부드러움을 제어하는 밴드폭(km/h)입니다.")



# === (간단 예측) 혼잡도 지수 산출: 4사분면 KPI용 ===
baseline_congestion = float(np.random.uniform(45, 65))
people_per_household = 2.3

delta_households = max(
    0,
    (desired_households - int(current["households"])) if pd.notna(current["households"]) else desired_households
)
added_population = delta_households * people_per_household * (1 + expected_pop_increase_ratio / 100)

alpha, beta = 0.004, 0.0006
congestion_delta = alpha * added_population - beta * (new_bus_count * bus_capacity)
predicted_congestion = max(0.0, min(100.0, baseline_congestion + congestion_delta))




# -------------------------------------------------------------
# 💹 4사분면 · 기대효과
# -------------------------------------------------------------
with col4:
    st.markdown("### 💹 4사분면 · 기대효과 & 리포트")

    price_per_py = st.number_input("평당 분양가/매매가(만원)", 1000, 100000, 4800, 100)
    cost_per_py = st.number_input("평당 총비용(만원)", 500, 80000, 3100, 100)

    unit_py = desired_py
    margin_per_unit_million = (price_per_py - cost_per_py) * unit_py
    expected_margin_billion = (margin_per_unit_million * desired_households) / 10000

    kcol1, kcol2, kcol3 = st.columns(3)
    with kcol1:
        st.markdown(f"<div class='kpi-card'><div class='kpi-title'>예상 수익(총)</div><div class='kpi-value'>{expected_margin_billion:.1f} 십억</div></div>", unsafe_allow_html=True)
    with kcol2:
        st.markdown(f"<div class='kpi-card'><div class='kpi-title'>혼잡도 지수(예측)</div><div class='kpi-value'>{predicted_congestion:.1f}</div></div>", unsafe_allow_html=True)
    with kcol3:
        st.markdown(f"<div class='kpi-card'><div class='kpi-title'>신규 세대수</div><div class='kpi-value'>{desired_households:,} 세대</div></div>", unsafe_allow_html=True)
