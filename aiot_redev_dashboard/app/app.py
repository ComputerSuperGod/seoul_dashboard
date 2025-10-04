# app.py
# -------------------------------------------------------------
# 🏗 AIoT 스마트 인프라 대시보드 (재건축 의사결정 Helper)
# -------------------------------------------------------------
# 이 파일은 데이터/API 연결 전까지 동작 가능한 Streamlit 스켈레톤입니다.
# 실제 데이터/API 연동 포인트는 [API HOOK] 주석으로 명확히 표시했습니다.
# -------------------------------------------------------------

import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import altair as alt
from datetime import datetime
from pathlib import Path

# ✅ 프로젝트 루트 기준 경로 자동 설정
BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "data" / "seoul_redev_projects.csv"
CSV_ENCODING = "cp949"

st.set_page_config(
    page_title="AIoT 스마트 인프라 대시보드 | 재건축 Helper",
    layout="wide",
)

# csv불러오기
if CSV_PATH.exists():
    df = pd.read_csv(CSV_PATH, encoding=CSV_ENCODING)
    st.success(f"✅ 데이터 파일 불러오기 완료: {CSV_PATH.name}")
    st.dataframe(df.head(20))  # 상위 20행 미리보기
else:
    st.error(f"❌ CSV 파일을 찾을 수 없습니다.\n아래 경로에 파일이 있어야 합니다:\n{CSV_PATH}")



# -------------------------------------------------------------
# ✅ 전역 스타일
# -------------------------------------------------------------
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
# 🧰 MOCK 데이터 (API/DB 연동 전 임시)
# -------------------------------------------------------------
# [API HOOK] 서울시 구경계 GeoJSON/Shape + 노후아파트 실데이터로 교체 필요
# - 서울시 행정구역 GeoJSON: data.seoul.go.kr
# - 노후아파트(준공연도, 세대수, 부지면적 등): 국토부 실거래/공공데이터 포털
# - 토지이음(부지면적/지목/용도지역): land.eum.go.kr
# - 평당 매매가: 국토부 실거래가 API 혹은 민간 시세 API
# - 교통혼잡/링크별 OD: KTDB View-T API (selectedLink_road.do)

DISTRICTS = [
    "강남구", "서초구", "송파구", "영등포구", "마포구", "성동구", "관악구", "구로구"
]

np.random.seed(42)

def mock_apartments_for(gu: str) -> pd.DataFrame:
    base_latlon = {
        "강남구": (37.4979, 127.0276),
        "서초구": (37.4836, 127.0326),
        "송파구": (37.5145, 127.1068),
        "영등포구": (37.5264, 126.8963),
        "마포구": (37.5638, 126.9084),
        "성동구": (37.5633, 127.0369),
        "관악구": (37.4784, 126.9516),
        "구로구": (37.4955, 126.8876),
    }
    lat0, lon0 = base_latlon.get(gu, (37.55, 127.0))
    n = 8
    data = []
    for i in range(n):
        lat = lat0 + np.random.normal(scale=0.01)
        lon = lon0 + np.random.normal(scale=0.01)
        built_year = int(np.random.choice(range(1975, 1998)))
        households = int(np.random.choice([120, 240, 360, 480, 600]))
        land_area_m2 = int(np.random.choice([8000, 12000, 15000, 22000]))
        name = f"{gu} 노후아파트 {i+1}"
        data.append({
            "gu": gu,
            "apt_id": f"{gu[:2]}-{i+1:02d}",
            "name": name,
            "lat": lat,
            "lon": lon,
            "built_year": built_year,
            "households": households,
            "land_area_m2": land_area_m2,
        })
    df = pd.DataFrame(data)
    return df

# 캐시: 구 선택 바뀔 때마다 재생성
@st.cache_data(show_spinner=False)
def get_mock_df(gu: str) -> pd.DataFrame:
    return mock_apartments_for(gu)

# -------------------------------------------------------------
# 🧭 사이드바
# -------------------------------------------------------------
st.sidebar.title("재건축 의사결정 Helper")
selected_gu = st.sidebar.selectbox("구 선택", DISTRICTS, index=0)
st.sidebar.markdown(
    "<div class='small-muted'>구 선택 시, 해당 구의 노후 아파트 목록과 지도 표시가 갱신됩니다.</div>",
    unsafe_allow_html=True,
)

# [API HOOK] 사용자 인증/권한, 프로젝트 저장/불러오기 기능
project_name = st.sidebar.text_input("프로젝트 이름", value=f"{selected_gu} 재건축 시나리오")

# -------------------------------------------------------------
# 📍 1-2사분면 (통합): 지도 + 단지 선택 + 입력패널 토글
# -------------------------------------------------------------
col12_left, col12_right = st.columns([2.2, 1.4], gap="large")

with col12_left:
    st.markdown("### 🗺 1-2사분면 · 지도 & 단지선택")
    df = get_mock_df(selected_gu)

    # 지도 (pydeck)
    view_state = pdk.ViewState(latitude=df["lat"].mean(), longitude=df["lon"].mean(), zoom=12)
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position='[lon, lat]',
        get_radius=60,
        pickable=True,
        elevation_scale=4,
        get_fill_color=[255, 140, 0],
    )
    tooltip = {
        "html": "<b>{name}</b><br/>준공연도: {built_year}<br/>세대수: {households}<br/>부지면적(m²): {land_area_m2}",
        "style": {"backgroundColor": "#0f172a", "color": "white"},
    }
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip))

    st.markdown("**단지 목록**")
    apt_display = df[["apt_id", "name", "built_year", "households", "land_area_m2"]]
    selected_row = st.radio(
        label="재건축 대상 단지 선택",
        options=apt_display.index.tolist(),
        format_func=lambda i: f"{apt_display.loc[i,'name']} · ({apt_display.loc[i,'built_year']}년 준공, {apt_display.loc[i,'households']}세대)",
        horizontal=False,
    )

with col12_right:
    st.markdown("### 🧾 1사분면 · 신설조건 입력")

    # 기존 단지 정보
    current = df.loc[selected_row]
    with st.container(border=True):
        st.markdown("**기존 단지 정보**")
        st.markdown(
            f"- 단지명: **{current['name']}**\n\n"
            f"- 준공연도: **{current['built_year']}**년\n\n"
            f"- 기존 세대수: **{current['households']} 세대**\n\n"
            f"- 부지면적: **{current['land_area_m2']:,} m²**"
        )
        st.markdown(
            "<div class='small-muted'>[API HOOK] 실데이터로 대체: 재건축 승인/허가 상태, 용도지역, 용적률, 건폐율, 정비구역 등</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

    # 신설 조건 입력
    st.markdown("**신설 계획 입력**")
    desired_py = st.number_input("원하는 전용 평형(평)", min_value=15, max_value=60, value=34, step=1)
    desired_households = st.number_input("원하는 세대수(신규)", min_value=100, max_value=3000, value=int(current["households"]) + 200, step=50)
    expected_pop_increase_ratio = st.slider("예상 인구증가율(%)", min_value=0, max_value=100, value=15, step=5)

    st.markdown(
        "<div class='small-muted'>[API HOOK] 평당 매매가/분양가, 건축비(표준단가), 금융비용, 인허가비 반영</div>",
        unsafe_allow_html=True,
    )

    # 버스/대중교통 변수 (간이)
    st.markdown("**대중교통 보완(가정)**")
    new_bus_count = st.slider("신설 버스 대수", 0, 20, 2, 1)
    bus_capacity = st.number_input("버스 1대 수용 인원(명)", min_value=30, max_value=120, value=70, step=5)
    st.markdown(
        "<div class='small-muted'>[API HOOK] 노선 개설 기준/정책, 좌석수, 배차, BRT/지하철 영향 반영 (KTDB/지자체 데이터)</div>",
        unsafe_allow_html=True,
    )

# -------------------------------------------------------------
# 📊 3사분면 · 혼잡도 분석 (모형: 간이 시뮬레이션)
# -------------------------------------------------------------
col3, col4 = st.columns([1.6, 1.4], gap="large")

with col3:
    st.markdown("### 🚦 3사분면 · 혼잡도 증가 예측")

    # 간이 추정 모델
    # - baseline_congestion: 0~100 지수 (구 단위 가상값)
    # - 인구증가와 버스공급에 따른 순효과 = alpha * 인구증가 - beta * (버스수*수용인원)
    # - [API HOOK] 실제는 링크/시간대별 혼잡지표 (KTDB View-T) + TAZ/OD 기반 배분 필요

    baseline_congestion = float(np.random.uniform(45, 65))  # 구 단위 베이스라인 지수 (가상)
    people_per_household = 2.3  # [API HOOK] 통계청/행안부 자료 반영 가능

    delta_households = max(0, desired_households - int(current["households"]))
    added_population = delta_households * people_per_household * (1 + expected_pop_increase_ratio / 100)

    alpha = 0.004  # 인구증가 민감도 (가상)
    beta = 0.0006  # 버스공급 완화계수 (가상)

    congestion_delta = alpha * added_population - beta * (new_bus_count * bus_capacity)
    predicted_congestion = max(0.0, min(100.0, baseline_congestion + congestion_delta))

    # 시간대별 곡선 (가상)
    hours = np.arange(6, 23)
    base_curve = np.clip(np.sin((hours-7)/4) * 20 + baseline_congestion, 10, 95)
    after_curve = np.clip(base_curve + congestion_delta, 0, 100)

    chart_df = pd.DataFrame({
        "hour": hours,
        "Baseline": base_curve,
        "After": after_curve,
    })
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

    with st.container():
        st.markdown("#### 가정과 한계")
        st.markdown("""
        - 본 예측은 **간이 가정**에 기반합니다. 실제 분석 시, 다음을 반영해야 합니다.
        1) **KTDB View-T API**의 링크/시간대별 혼잡지표 및 OD 데이터를 이용한 세부 배분
        2) **노선 신설 정책**(노선 개설 기준, 배차, 차량용량)과 **대체 교통수단** 영향
        3) **공사기간 중 교통영향** 및 단계별 입주 시나리오
        4) **부지 용적률/건폐율**, 주차, 출입구 배치에 따른 마이크로 교통 영향
        """)

# -------------------------------------------------------------
# 💹 4사분면 · 기대효과/예상 이익 (간이)
# -------------------------------------------------------------
with col4:
    st.markdown("### 💹 4사분면 · 기대효과 & 리포트")

    # 간이 수익성: (분양/매매가 - 비용) * 세대수
    # [API HOOK] 평당 매매가/분양가, 표준건축비, 금융비용, 인허가/세금, 기반시설 부담 포함 모델로 대체
    price_per_py = st.number_input("평당 분양가/매매가(만원)", min_value=1000, max_value=100000, value=4800, step=100)
    cost_per_py = st.number_input("평당 총비용(만원)", min_value=500, max_value=80000, value=3100, step=100)

    unit_py = desired_py
    margin_per_unit_million = (price_per_py - cost_per_py) * unit_py  # 만원*평
    expected_margin_billion = (margin_per_unit_million * desired_households) / 10000  # 억→십억 단위

    st.markdown("#### KPI")
    kcol1, kcol2, kcol3 = st.columns(3)
    with kcol1:
        st.markdown("<div class='kpi-card'><div class='kpi-title'>예상 수익(총)</div>" \
                    f"<div class='kpi-value'>{expected_margin_billion:.1f} 십억</div></div>", unsafe_allow_html=True)
    with kcol2:
        st.markdown("<div class='kpi-card'><div class='kpi-title'>혼잡도 지수(예측)</div>" \
                    f"<div class='kpi-value'>{predicted_congestion:.1f}</div></div>", unsafe_allow_html=True)
    with kcol3:
        st.markdown("<div class='kpi-card'><div class='kpi-title'>신규 세대수</div>" \
                    f"<div class='kpi-value'>{desired_households:,} 세대</div></div>", unsafe_allow_html=True)

    st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

    st.markdown("#### 리포트 미리보기")
    report_md = f"""
**프로젝트명**: {project_name}

**대상 구**: {selected_gu}  
**대상 단지**: {current['name']} ({current['built_year']}년 준공, {current['households']}세대)  
**부지면적**: {current['land_area_m2']:,} m²  

---
### 신설 계획
- 전용 평형: **{desired_py}평**  
- 세대수(신규): **{desired_households:,} 세대**  
- 예상 인구증가율: **{expected_pop_increase_ratio}%**  
- 버스 신설: **{new_bus_count}대**, 1대 수용 **{bus_capacity}명**  

### 교통 혼잡도 (간이)
- 베이스라인 지수(가정): **{baseline_congestion:.1f}**  
- 예측 지수(시나리오): **{predicted_congestion:.1f}**  

### 수익성 (간이)
- 평당 분양/매매가: **{price_per_py}만원/평**  
- 평당 총비용: **{cost_per_py}만원/평**  
- 세대당 마진(가정): **{margin_per_unit_million * 1:.0f}만원/세대**  
- 총 기대 수익(가정): **{expected_margin_billion:.1f} 십억**  

> ⚠️ 본 수치는 예시이며 실제 인허가, 시장가격, 건축비, 금융비용, 교통영향평가 결과 등에 따라 크게 달라질 수 있습니다.

---
**데이터/API 연동 예정**  
- [API HOOK] 재건축 승인·허가 단지 목록(주소·지번·고유ID)  
- [API HOOK] 토지이음(부지면적/지목/용도/용적률/건폐율)  
- [API HOOK] 평당 매매가/분양가(국토부 실거래·민간시세)  
- [API HOOK] KTDB View-T 혼잡도/OD (링크ID·연도·시간대·평일/주말)  
- [API HOOK] 버스 노선 개설 기준·수용력·배차 정보
"""

    st.markdown(report_md)

    st.download_button(
        label="리포트 다운로드 (Markdown)",
        data=report_md,
        file_name=f"{project_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.md",
        mime="text/markdown",
    )

# -------------------------------------------------------------
# 🧩 개발 가이드 (요약)
# -------------------------------------------------------------
with st.expander("🔧 데이터/API 연동 가이드 (요약)"):
    st.markdown("""
**1) 재건축 대상 아파트**  
- [API HOOK] 공공데이터 포털/지자체 고시/정비구역 DB 연계 → `df` 스키마(`apt_id, name, lat, lon, built_year, households, land_area_m2, ...`) 정규화

**2) 토지이음**  
- [API HOOK] 지번 기준 크롤/스크래핑 또는 제공 API로 용적률/건폐율/용도지역 취득 → 신설 가능 세대수 산정 로직 반영

**3) 평당 가격**  
- [API HOOK] 국토부 실거래가(매매/분양) API → 단지/권역 매핑 후 가격 보정(시점/면적/층/브랜드 등) 모델링

**4) 교통 혼잡도/OD**  
- [API HOOK] KTDB View-T `selectedLink_road.do` 등 → 링크ID·연도·시간대·평일/주말 인자 바인딩, 선택 구역 주변 대표 링크 묶음 집계

**5) 버스 노선/용량**  
- [API HOOK] 지자체(버스정책과) 기준표 + 노선 개설 규정·BRT 여부·배차간격 입력값 반영

**6) 시나리오 저장/불러오기**  
- [API HOOK] 사용자/프로젝트/시나리오 스키마 설계 (RDB 또는 파이어스토어) + 인증
""")

st.caption("© 2025 AIoT 스마트 인프라 대시보드 — Streamlit 스켈레톤 (데모)")
