# -------------------------------------------------------------
# 🏗 AIoT 스마트 인프라 대시보드 (재건축 의사결정 Helper)
# -------------------------------------------------------------
# 📊 CSV 기반 데이터 반영 버전
# -------------------------------------------------------------

import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import altair as alt
from datetime import datetime
from pathlib import Path

# 🔤 안전한 CSV 로더: 여러 인코딩 시도
def smart_read_csv(path, encodings=("utf-8-sig", "cp949", "euc-kr", "utf-8", "latin1")):
    import pandas as pd
    last_err = None
    for enc in encodings:
        try:
            df = pd.read_csv(path, encoding=enc)
            try:
                import streamlit as st
                st.caption(f"📄 Loaded {path.name} with encoding = **{enc}**")
            except Exception:
                pass
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
COORD_CSV_PATH = BASE_DIR / "data" / "서울시_재개발재건축_좌표포함.csv"
COORD_ENCODING = "cp949"

@st.cache_data(show_spinner=False)
def load_coords() -> pd.DataFrame:
    df = smart_read_csv(COORD_CSV_PATH)
    df["lat"] = pd.to_numeric(df.get("lat"), errors="coerce")
    df["lon"] = pd.to_numeric(df.get("lon"), errors="coerce")

    def _coalesce(*vals):
        for v in vals:
            if pd.notna(v) and str(v).strip():
                return v
        return None

    df_norm = pd.DataFrame({
        "apt_id": df.get("사업번호").astype(str) if "사업번호" in df.columns else None,
        "name": [_coalesce(n, m) for n, m in zip(df.get("정비구역명칭"), df.get("추진위원회/조합명"))],
        "gu": df.get("자치구"),
        "address": [_coalesce(a, b) for a, b in zip(df.get("정비구역위치"), df.get("대표지번"))],
        "lat": df["lat"],
        "lon": df["lon"],
    })
    df_norm["apt_id"] = df_norm["apt_id"].fillna("").astype(str)
    df_norm["name"] = df_norm["name"].fillna("")
    df_norm["address"] = df_norm["address"].fillna("")
    return df_norm


# 서울 자치구 중심좌표 (간이값)
GU_CENTER = {
    "강남구": (37.5172, 127.0473),
    "서초구": (37.4836, 127.0326),
    "송파구": (37.5145, 127.1068),
    "영등포구": (37.5264, 126.8963),
    "마포구": (37.5638, 126.9084),
    "성동구": (37.5633, 127.0369),
    "관악구": (37.4784, 126.9516),
    "구로구": (37.4955, 126.8876),
}


@st.cache_data(show_spinner=False)
def merge_projects_with_coords(gu: str) -> pd.DataFrame:
    # 1) 원본 로드 + 스키마 통일
    raw = load_raw_csv()
    proj = normalize_schema(raw)              # ✅ apt_id, name, gu, address, households, land_area_m2 생성
    proj = proj[proj["gu"] == gu].copy()

    # 2) 좌표 로드
    coords = load_coords()
    coords = coords[coords["gu"] == gu].copy()

    # 3) 병합: 우선 name→(보강 필요 시) apt_id/address 키 확장 가능
    out = proj.merge(coords[["name","lat","lon"]], on="name", how="left")

    # 4) 좌표 결측 보정 (구 중심 + 지터)
    missing = out["lat"].isna() | out["lon"].isna()
    base_lat, base_lon = GU_CENTER.get(gu, (37.55, 127.0))
    rng = np.random.default_rng(42)
    jitter = lambda n: rng.normal(0, 0.002, n)  # ≈ 200m 분산
    if missing.any():
        n = int(missing.sum())
        out.loc[missing, "lat"] = base_lat + jitter(n)
        out.loc[missing, "lon"] = base_lon + jitter(n)
    out["has_geo"] = ~missing

    return out.reset_index(drop=True)


# -------------------------------------------------------------
# ⚙️ Streamlit 기본 설정
# -------------------------------------------------------------
st.set_page_config(
    page_title="AIoT 스마트 인프라 대시보드 | 재건축 Helper",
    layout="wide",
)

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

# -------------------------------------------------------------
# 🧾 CSV 로드 & 전처리
# -------------------------------------------------------------
@st.cache_data(show_spinner=False)
# -------------------------------------------------------------
# 🧾 CSV 로드 & 전처리
# -------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_raw_csv() -> pd.DataFrame:
    return smart_read_csv(CSV_PATH)  # ✅ 인코딩 자동 감지 사용

def _coalesce(*vals):
    for v in vals:
        if pd.notna(v) and str(v).strip():
            return v
    return None

def normalize_schema(df_raw: pd.DataFrame) -> pd.DataFrame:
    c = df_raw.columns
    get = lambda name: df_raw[name] if name in c else pd.Series([None]*len(df_raw))

    df = pd.DataFrame({
        "apt_id": get("사업번호"),
        "name": [_coalesce(n, m) for n, m in zip(get("정비구역명칭"), get("추진위원회/조합명"))],
        "gu": get("자치구"),
        "address": [_coalesce(a, b) for a, b in zip(get("정비구역위치"), get("대표지번"))],
        "households": pd.to_numeric(get("분양세대총수"), errors="coerce"),
        "land_area_m2": pd.to_numeric(get("정비구역면적(㎡)"), errors="coerce"),
    })
    df["apt_id"] = df["apt_id"].astype(str)
    df["name"] = df["name"].fillna("무명 정비구역")
    df["gu"] = df["gu"].fillna("미상")
    df["address"] = df["address"].fillna("")
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
selected_gu = st.sidebar.selectbox("구 선택", DISTRICTS, index=0)
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
st.markdown("**단지 목록**")

# 숫자 컬럼 정리
df_list = df_map[["apt_id", "name", "households", "land_area_m2"]].copy()
df_list["households"] = pd.to_numeric(df_list["households"], errors="coerce")
df_list["land_area_m2"] = pd.to_numeric(df_list["land_area_m2"], errors="coerce")

# ===== 필터 영역 =====
fcol1, fcol2, fcol3, fcol4 = st.columns([1.6, 1.4, 1.6, 1.2])

with fcol1:
    kw = st.text_input("검색어(단지명/키워드)", value="", placeholder="예) 목동, 신월, 재건축")

with fcol2:
    hh_min = int(np.nan_to_num(df_list["households"].min(), nan=0))
    hh_max = int(np.nan_to_num(df_list["households"].max(), nan=0))
    households_range = st.slider("세대수 범위", min_value=0, max_value=max(hh_max, 100), value=(0, max(hh_max, 100)))

with fcol3:
    la_min = float(np.nan_to_num(df_list["land_area_m2"].min(), nan=0.0))
    la_max = float(np.nan_to_num(df_list["land_area_m2"].max(), nan=0.0))
    land_range = st.slider(
        "면적 범위(m²)",
        min_value=0,
        max_value=int(max(la_max, 0)),
        value=(0, int(max(la_max, 0)))
    )

with fcol4:
    hide_zero = st.checkbox("0/결측치 숨기기", value=True)

# ===== 필터 적용 =====
mask = pd.Series(True, index=df_list.index)

if kw.strip():
    _kw = kw.strip().lower()
    mask &= df_list["name"].fillna("").str.lower().str.contains(_kw)

# 세대수 필터
mask &= df_list["households"].fillna(-1).between(households_range[0], households_range[1], inclusive="both")

# 면적 필터
mask &= df_list["land_area_m2"].fillna(-1).between(land_range[0], land_range[1], inclusive="both")

# 0/결측치 숨기기
if hide_zero:
    mask &= df_list["households"].fillna(0) > 0
    mask &= df_list["land_area_m2"].fillna(0) > 0

filtered = df_list[mask].reset_index().rename(columns={"index": "orig_index"})  # orig_index는 df_map 인덱스 보존용

# ===== 정렬 옵션 =====
scol1, scol2 = st.columns([1.2, 1.2])
with scol1:
    sort_key = st.selectbox("정렬 기준", ["세대수 내림차순", "세대수 오름차순", "면적 내림차순", "면적 오름차순", "이름 오름차순"], index=0)
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
elif sort_key == "이름 오름차순":
    filtered = filtered.sort_values("name", ascending=True, na_position="last")

if topn != "전체":
    filtered = filtered.head(int(topn))

# ===== 테이블 표시 =====

show_df = filtered[["orig_index", "name", "households", "land_area_m2"]].copy()
show_df = show_df.rename(columns={
    "name": "단지명",
    "households": "세대수",
    "land_area_m2": "면적(m²)"
})

st.dataframe(
    show_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "orig_index": st.column_config.NumberColumn("원본인덱스", help="내부 선택용", width="small"),
        "단지명": st.column_config.TextColumn("단지명"),
        "세대수": st.column_config.NumberColumn("세대수", format="%,d"),
        "면적(m²)": st.column_config.NumberColumn("면적(m²)", format="%,d"),
    }
)

# ===== 선택 위젯 (테이블과 동기화) =====
if filtered.empty:
    st.info("조건에 맞는 단지가 없습니다. 필터를 조정해보세요.")
    st.stop()

selected_orig_index = st.selectbox(
    "정비사업 단지 선택",
    options=filtered["orig_index"].tolist(),
    format_func=lambda i: f"{df_map.loc[i,'name']} · ({int(df_map.loc[i,'households']) if pd.notna(df_map.loc[i,'households']) else 0}세대, {df_map.loc[i,'land_area_m2'] if pd.notna(df_map.loc[i,'land_area_m2']) else '-'}㎡)"
)

# ---- 기존 로직과의 연결을 위해 selected_row를 원본 인덱스로 세팅 ----
selected_row = int(selected_orig_index)

# ✅ 선택 단지 선택 이후 지도 표시 코드 (이 위치로 옮기세요!)
filtered_indices = filtered["orig_index"].tolist()
map_data = df_map.loc[filtered_indices].reset_index(drop=True)

# 선택된 단지의 좌표 (지도 중심 이동용)
sel_lat = float(df_map.loc[selected_row, "lat"])
sel_lon = float(df_map.loc[selected_row, "lon"])

# 지도 뷰 설정
view_state = pdk.ViewState(latitude=sel_lat, longitude=sel_lon, zoom=12.5)

# 필터된 단지 표시
layer_points = pdk.Layer(
    "ScatterplotLayer",
    data=map_data,
    get_position='[lon, lat]',
    get_radius=60,
    pickable=True,
    get_fill_color=[255, 140, 0, 160],  # 주황
    get_line_color=[255, 255, 255],
    line_width_min_pixels=0.5,
)

# 선택 단지 하이라이트
highlight_row = df_map.loc[[selected_row]].assign(_selected=True)
layer_highlight = pdk.Layer(
    "ScatterplotLayer",
    data=highlight_row,
    get_position='[lon, lat]',
    get_radius=150,
    pickable=False,
    get_fill_color=[0, 200, 255, 220],  # 청록
    get_line_color=[0, 0, 0],
    line_width_min_pixels=1.2,
)

tooltip = {
    "html": "<b>{name}</b><br/>자치구: {gu}<br/>세대수: {households}<br/>구역면적(m²): {land_area_m2}",
    "style": {"backgroundColor": "#0f172a", "color": "white"},
}

# map_slot은 위에서 col12_left에 이미 정의되어 있음
if map_data.empty:
    st.info("조건에 맞는 단지가 없습니다. 필터를 조정해보세요.")
    map_slot.pydeck_chart(pdk.Deck(layers=[layer_highlight], initial_view_state=view_state, tooltip=tooltip))
else:
    map_slot.pydeck_chart(pdk.Deck(layers=[layer_points, layer_highlight], initial_view_state=view_state, tooltip=tooltip))

with col12_right:
    st.markdown("### 🧾 1사분면 · 신설조건 입력")
    current = df_map.loc[selected_row]
    with st.container(border=True):
        st.markdown("**기존 단지 정보**")
        st.markdown(
            f"- 단지명: **{current['name']}**\n\n"
            f"- 자치구: **{current['gu']}**\n\n"
            f"- 기존 세대수: **{int(current['households']) if pd.notna(current['households']) else '미상'} 세대**\n\n"
            f"- 정비구역면적: **{int(current['land_area_m2']):,} m²**"
        )

    st.markdown("<hr class='soft'/>", unsafe_allow_html=True)
    desired_py = st.number_input("원하는 전용 평형(평)", min_value=15, max_value=60, value=34, step=1)
    desired_households = st.number_input("원하는 세대수(신규)", min_value=100, max_value=3000,
                                         value=int(current["households"]) + 200 if pd.notna(current["households"]) else 500, step=50)
    expected_pop_increase_ratio = st.slider("예상 인구증가율(%)", 0, 100, 15, 5)
    new_bus_count = st.slider("신설 버스 대수", 0, 20, 2, 1)
    bus_capacity = st.number_input("버스 1대 수용 인원(명)", min_value=30, max_value=120, value=70, step=5)

# -------------------------------------------------------------
# 🚦 3사분면 · 혼잡도 예측
# -------------------------------------------------------------
col3, col4 = st.columns([1.6, 1.4], gap="large")

with col3:
    st.markdown("### 🚦 3사분면 · 혼잡도 증가 예측")

    baseline_congestion = float(np.random.uniform(45, 65))
    people_per_household = 2.3
    delta_households = max(0, desired_households - int(current["households"]))
    added_population = delta_households * people_per_household * (1 + expected_pop_increase_ratio / 100)
    alpha, beta = 0.004, 0.0006
    congestion_delta = alpha * added_population - beta * (new_bus_count * bus_capacity)
    predicted_congestion = max(0.0, min(100.0, baseline_congestion + congestion_delta))

    hours = np.arange(6, 23)
    base_curve = np.clip(np.sin((hours-7)/4) * 20 + baseline_congestion, 10, 95)
    after_curve = np.clip(base_curve + congestion_delta, 0, 100)
    chart_df = pd.DataFrame({"hour": hours, "Baseline": base_curve, "After": after_curve})
    chart_long = chart_df.melt("hour", var_name="Scenario", value_name="CongestionIndex")

    line = (
        alt.Chart(chart_long)
        .mark_line(point=True)
        .encode(
            x=alt.X("hour:O", title="시간대"),
            y=alt.Y("CongestionIndex:Q", title="혼잡도 지수(0~100)"),
            color=alt.Color("Scenario:N", legend=alt.Legend(title="시나리오")),
            tooltip=["hour", "Scenario", alt.Tooltip("CongestionIndex", format=".1f")],
        )
        .properties(height=360)
    )
    st.altair_chart(line, use_container_width=True)

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
