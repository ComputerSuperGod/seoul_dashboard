# pages/8_핵심기술.py
# 🔧 AIoT 스마트 인프라 대시보드 — 핵심 기술 정리 & 미니 데모

from __future__ import annotations
import numpy as np
import pandas as pd
import streamlit as st
import altair as alt

st.set_page_config(page_title="핵심 기술 | AIoT 스마트 인프라 대시보드", layout="wide")

# ────────────────────────────────────────────────────────────────
# 공통 스타일
# ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.katex-display { text-align: left !important; margin-left: 0 !important; }
.block-container { text-align: left !important; }
.small-muted { color: #7a7a7a; font-size: 0.9rem; }
.kpi-card { padding: 14px; border-radius: 14px; background: #111827; border: 1px solid #1f2937; }
.kpi-title { font-size: 0.9rem; color: #9ca3af; margin-bottom: 6px; }
.kpi-value { font-size: 1.15rem; font-weight: 700; color: #e5e7eb; }
.section-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 8px; }
hr.soft { border: none; height: 1px; background: #1f2937; margin: 16px 0; }
</style>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────────
# 헤더
# ────────────────────────────────────────────────────────────────
st.title("🔧 핵심 기술")
st.caption("혼잡도 모델링 · 데이터 정규화/파이프라인 · 지오비주얼 · 재무 KPI · 성능 최적화 · 신뢰성/검증을 한 곳에 요약합니다.")

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown("<div class='kpi-card'><div class='kpi-title'>모델</div><div class='kpi-value'>혼잡%·w(h)·완급</div></div>", unsafe_allow_html=True)
with c2:
    st.markdown("<div class='kpi-card'><div class='kpi-title'>데이터</div><div class='kpi-value'>엑셀→CSV 정규화</div></div>", unsafe_allow_html=True)
with c3:
    st.markdown("<div class='kpi-card'><div class='kpi-title'>지오</div><div class='kpi-value'>SHP 매칭·GeoJSON</div></div>", unsafe_allow_html=True)
with c4:
    st.markdown("<div class='kpi-card'><div class='kpi-title'>성능/품질</div><div class='kpi-value'>캐시·검증·테스트</div></div>", unsafe_allow_html=True)

st.divider()

# ────────────────────────────────────────────────────────────────
# Tabs
# ────────────────────────────────────────────────────────────────
t1, t2, t3, t4, t5, t6 = st.tabs([
    "① 교통 영향 추정(모델)",
    "② 데이터 파이프라인/정규화",
    "③ 지오스택(로딩·매칭·렌더)",
    "④ 재무 KPI(시나리오)",
    "⑤ 성능 최적화",
    "⑥ 신뢰성/검증"
])

# =================================================================
# ① 교통 영향 추정(모델)
# =================================================================
with t1:
    st.subheader("① 교통 영향 추정(혼잡% 모델 + 시간대 가중 w(h))")

    st.markdown("**혼잡도(%) 변환** — 링크 `l`, 시간대 `h`에서 평균속도 $v_{l,h}$, 자유주행속도 $v_{ff,l} = \\max_h v_{l,h}$ 일 때")
    st.latex(r"""\mathrm{Cong}_{l,h}(\%) = \Big(1 - \min(1, \frac{v_{l,h}}{v_{ff,l}})\Big)\times 100""")

    st.markdown("**재건축 후 혼잡 추정(시간대 가중 반영)**")
    st.latex(r"""
    \text{after}(h)= 100 \times 
    \left[
        1 - \frac{1 - \dfrac{\text{base}(h)}{100}}{1 + \eta\,\tilde{w}(h)\,(r - 1)}
    \right]
    """)
    st.caption("- $r = \\dfrac{\\text{계획세대수}}{\\text{기존세대수}},\\; \\eta$: 구별 민감도, $\\tilde{w}(h)$: 시간대 가중치(피크≈1, 심야↓)")

    # ── 미니 데모: synthetic base curve + parameters
    st.markdown("#### 🎛 미니 데모")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        eta = st.slider("민감도 η", 0.2, 1.2, 0.6, 0.05)
    with c2:
        r = st.slider("세대 증가비 r", 0.5, 2.0, 1.25, 0.05)
    with c3:
        dawn_min = st.slider("새벽 최소 가중(min_factor)", 0.0, 1.0, 0.2, 0.05)
    with c4:
        turn = st.slider("회복 중심 시각", 5.0, 9.0, 6.5, 0.5)

    h = np.arange(24, dtype=float)

    # Synthetic base congestion curve: AM/PM peaks
    def base_curve(hh: np.ndarray) -> np.ndarray:
        am = 55*np.exp(-0.5*((hh-8.0)/1.6)**2)
        pm = 65*np.exp(-0.5*((hh-18.0)/2.0)**2)
        off = 15 + 5*np.sin((hh-11)/24*2*np.pi)
        return np.clip(am + pm + off, 0, 100)

    base = base_curve(h)

    # Dawn smoothing weight
    def dawn_smoothing(w_hour: np.ndarray, min_factor: float = 0.55, turn_hour: float = 7.5, k: float = 0.9) -> np.ndarray:
        return w_hour * (min_factor + (1.0 - min_factor)/(1.0 + np.exp(-k*(h - turn_hour))))

    w_hour = dawn_smoothing(np.ones_like(h), min_factor=float(dawn_min), turn_hour=float(turn), k=1.6)

    after = 100.0 * (1.0 - (1.0 - base/100.0) / (1.0 + eta*w_hour*(r-1.0)))
    plot_df = pd.DataFrame({"hour": h, "기준 추세": base, "재건축 후(추정)": np.clip(after, 0, 100), "w(h)": w_hour})

    left, right = st.columns([1.4, 1.0])
    with left:
        ch = alt.Chart(plot_df.melt("hour", ["기준 추세","재건축 후(추정)"])) \
            .mark_line(point=True) \
            .encode(
                x=alt.X("hour:Q", title="시간대(시)"),
                y=alt.Y("value:Q", title="혼잡도(%)", scale=alt.Scale(domain=[0,100])),
                color=alt.Color("variable:N", title="")
            ).properties(height=320, title="기준 vs 재건축 후(추정)")
        st.altair_chart(ch, use_container_width=True)
    with right:
        chw = alt.Chart(plot_df).mark_area(opacity=0.35).encode(
            x=alt.X("hour:Q", title="시간대(시)"),
            y=alt.Y("w(h):Q", title="가중치")
        ).properties(height=320, title="시간대 가중치 w(h)")
        st.altair_chart(chw, use_container_width=True)

    st.markdown("#### 🚍 최소 증편률(완화안) 폐쇄형 해")
    st.latex(r"""b_{\min} = 150 \cdot \max_h \max\left(0,\; 1 - \frac{\text{base}(h)}{\max(\text{after}(h),\;10^{-6})}\right)""")
    st.caption("균일 증편률 b(%)로 after×(1−b/150)을 내려 모든 시간대에서 base 이하가 되는 최소값을 산출.")

# =================================================================
# ② 데이터 파이프라인/정규화
# =================================================================
with t2:
    st.subheader("② 데이터 파이프라인/정규화 (Excel→CSV→시각화용 Long)")

    st.markdown("""
- **자동 레이아웃 탐지**: 보고서형 엑셀에서 *시간대 헤더(예: `0~1시`)* 를 찾아 wide→long 변환  
- **표준 키 통일**: `link_id` 로 표준화 → 이후 모든 처리(매칭/그래프)에서 일관성 유지  
- **시간대 파싱**: `"0~1시"` → `hour=0` 등, 시작 시각 정수화  
- **함수**: `convert_average_speed_excel_to_csv`, `ensure_speed_csv` (없으면 생성)
    """)

    st.code(
        """# utils/traffic_preproc.py 발췌
def convert_average_speed_excel_to_csv(xlsx_path, out_csv_path, prefer_id="5.5"):
    df0 = pd.read_excel(xlsx_path, header=None)
    base_r, time_r, time_c0, data_r0 = _detect_layout(df0)
    # ... wide → long & 'link_id' 표준화 ...
    df_long["hour"] = df_long["시간대"].map(to_hour_bucket).dropna().astype(int)
    df_long = df_long.rename(columns={link_col: "link_id"})
    df_long.to_csv(out_csv_path, index=False)
    return df_long

def ensure_speed_csv(xlsx_path, out_csv_path):
    if not Path(out_csv_path).exists():
        convert_average_speed_excel_to_csv(xlsx_path, out_csv_path)
    return out_csv_path
""",
        language="python",
    )

    st.info("📌 결과 CSV 스키마(요지): `link_id, 시간대, 평균속도(km/h), hour` — 이후 모든 시각화는 이 스키마를 가정합니다.")

# =================================================================
# ③ 지오스택(로딩·매칭·렌더)
# =================================================================
with t3:
    st.subheader("③ 지오스택: Shapefile 로딩·링크 매칭·GeoJSON 렌더")

    st.markdown("""
- **강건한 SHP 로더**: pyogrio/fiona × utf-8/cp949/euc-kr 등 여러 조합을 순차 시도  
- **좌표계 통일**: 가공은 3857(거리), 표시/병합은 4326  
- **ID 표준화**: `k_link_id` 등을 문자열 ID로 통일(`.0` 제거)  
- **GeoJSON 캐시 키 전략**: 세션엔 **키만** 보관, 실 데이터는 캐시(dict)에서 재참조
    """)

    st.code(
        """# utils/traffic_plot.py 발췌
def _read_shp_robust(shp_path):
    tries = [("pyogrio","utf-8",{}), ("pyogrio","cp949",{}), ... , ("fiona","euc-kr",{})]
    for engine, enc, extra in tries:
        try:
            return gpd.read_file(shp_path, engine=engine, encoding=enc, **extra)
        except Exception:
            continue
    raise RuntimeError("SHP 읽기 실패: 인코딩/엔진 조합 점검 필요")

# 반경 내 링크 추출 → CSV의 link_id 와 매칭 → 시간대 속도 차트
def get_nearby_speed_data(csv_path, shp_path, center_lon, center_lat, radius_m=1000, max_links=10):
    gdf = _read_shp_robust(shp_path).to_crs(epsg=4326).to_crs(epsg=3857)
    # 거리기반 필터링 + link_id 표준화 후 CSV와 매칭
    # ...
    return df_plot  # (link_id, hour, 평균속도)
""",
        language="python",
    )

    st.caption("※ 실제 지도 렌더는 `pydeck.GeoJsonLayer` + 선 색상(혼잡도)이며, 일평균/분위수 기준을 라디오로 전환.")

# =================================================================
# ④ 재무 KPI(시나리오)
# =================================================================
with t4:
    st.subheader("④ 재무 KPI/시나리오 계산 (간이)")

    st.markdown("**핵심 계산 항목**: 분양면적/예상 혼잡도/총매출/총사업비/이익/마진율/NPV/회수기간")

    st.code(
        """# app.py 발췌 (간이 KPI)
def calc_kpis(households, avg_py, sale_price_per_m2, build_cost_per_m2, infra_invest_billion,
              congestion_base, bus_inc_pct, non_sale_ratio=0.15, sale_rate=0.98, disc_rate=0.07, years=4):
    m2_per_py = 3.3058
    avg_m2 = avg_py * m2_per_py
    sellable_m2 = households * avg_m2 * (1 - non_sale_ratio)
    predicted_cong = max(0.0, congestion_base * (1 - bus_inc_pct / 150))
    # ... 매출·비용·NPV·회수기간 산출 ...
    return {...}
""",
        language="python",
    )

    st.markdown("#### 🎛 미니 계산기")
    lc, rc = st.columns([1.3, 1])
    with lc:
        households = st.slider("세대수", 200, 5000, 1200, 50)
        avg_py = st.slider("평균 전용(평)", 15.0, 45.0, 25.0, 0.5)
        sale = st.slider("분양가(만원/㎡)", 800.0, 2000.0, 1200.0, 10.0)
        cost = st.slider("공사비(만원/㎡)", 500.0, 1500.0, 900.0, 10.0)
        infra = st.slider("인프라(억원)", 0.0, 300.0, 30.0, 5.0)
        cong = st.slider("기준 혼잡도(%)", 0.0, 100.0, 50.0, 1.0)
        bus = st.slider("버스 증편(%)", 0, 100, 15, 5)
        sale_rate = st.slider("분양률", 0.85, 1.0, 0.98, 0.01)
        disc = st.slider("할인율", 0.03, 0.15, 0.07, 0.005)
        years = st.slider("회수기간(년)", 2, 10, 4, 1)
        non_sale = st.slider("비분양비율", 0.0, 0.4, 0.15, 0.01)

    def calc_kpis(households, avg_py, sale_price_per_m2, build_cost_per_m2, infra_invest_billion,
                  congestion_base, bus_inc_pct, non_sale_ratio=0.15, sale_rate=0.98, disc_rate=0.07, years=4):
        m2_per_py = 3.3058
        avg_m2 = avg_py * m2_per_py
        sellable_m2 = households * avg_m2 * (1 - non_sale_ratio)
        predicted_cong = max(0.0, float(congestion_base) * (1 - float(bus_inc_pct) / 150.0))
        cong_improve = max(0.0, float(congestion_base) - predicted_cong)
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

    kpis = calc_kpis(households, avg_py, sale, cost, infra, cong, bus, non_sale, sale_rate, disc, years)
    with rc:
        st.markdown("##### 결과")
        for k, v in kpis.items():
            st.metric(k, f"{v:,.1f}" if isinstance(v, (int,float)) else v)

# =================================================================
# ⑤ 성능 최적화
# =================================================================
with t5:
    st.subheader("⑤ 성능 최적화 전략")

    st.markdown("""
- **캐싱 계층화**  
  - `@st.cache_resource`: SHP(지오메트리), 내부 GeoJSON dict 저장  
  - `@st.cache_data`: CSV/가공 DataFrame, 일평균/랭크 등 결과  
- **세션에는 키만**: GeoJSON 실데이터는 캐시 dict, 세션엔 key만 저장  
- **dtype 최적화**: `category`/다운캐스트로 메모리 절감  
- **렌더 분리**: 지도·Altair 차트를 계산과 분리하여 불필요한 재계산 최소화  
- **방어적 코딩**: 결측/부재 파일 처리, `.0` 제거 등 ID 표준화  
- **벡터화**: 혼잡 변환/일평균/시그모이드 가중 일괄 계산
    """)

    st.code(
        """# GeoJSON 키 캐시 전략 (요지)
@st.cache_resource(show_spinner=False)
def _geojson_store() -> dict:
    return {}

def _geojson_cache_store(key: str, obj: dict) -> bool:
    _geojson_store()[key] = obj; return True

def _geojson_cache_get(key: str) -> dict | None:
    return _geojson_store().get(key)

# 세션에는 key만 보관 → 필요 시 캐시에서 GeoJSON 획득
key = build_daily_geojson_key(df_daily, color_mode)
st.session_state["matched_geo_key_daily"] = key
""",
        language="python",
    )

# =================================================================
# ⑥ 신뢰성/검증
# =================================================================
with t6:
    st.subheader("⑥ 신뢰성/검증 (Validation & Test)")

    st.markdown("""
**데이터 검증**
- 링크 ID 표준화: 문자열화 + `.0` 제거 + `{'0','-1',''}` 필터링  
- 시간대 파싱 유효성: `"\\d{1,2}~\\d{1,2}시"` 정규식, 시작시/종료시 범위(0–24) 체크  
- 속도값 범위: 음수/비정상(>200km/h) 제거 또는 클리핑  

**모형 검증**
- 자유주행속도 $v_{ff}$ = 시간대 최대속도 확인  
- 혼잡도 0–100% 경계 테스트  
- 완화해 $b_{min}$ 계산 시 after×(1−b/150) ≤ base 검증

**단위 테스트 (예시/pytest)**
```python
def test_hour_bucket():
    assert to_hour_bucket("0~1시") == 0
    assert to_hour_bucket("23~24시") == 23

def test_congestion_bounds():
    base = np.array([0, 50, 100])
    after = 100.0 * (1.0 - (1.0 - base/100.0) / (1.0 + 0.6*1.0*(1.2-1.0)))
    assert (after >= 0).all() and (after <= 100).all()
