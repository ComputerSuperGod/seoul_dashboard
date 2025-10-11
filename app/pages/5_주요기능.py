# pages/5_주요기능.py
# 🧰 AIoT 스마트 인프라 대시보드 — 주요 기능 안내 / 미니 데모

from __future__ import annotations
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np

# ────────────────────────────────────────────────────────────────
# 공통 스타일
# ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="주요 기능 | AIoT 스마트 인프라 대시보드", layout="wide")

st.markdown("""
<style>
.katex-display { text-align: left !important; margin-left: 0 !important; }
.block-container { text-align: left !important; }
div[data-testid="stMarkdownContainer"] .katex-display { text-align: left !important; margin-left: 0 !important; margin-right: auto !important; }
div[data-testid="stMarkdownContainer"] .katex-display > .katex { display: inline-block !important; }
.small-muted { color: #7a7a7a; font-size: 0.9rem; }
.kpi-card { padding: 16px; border-radius: 16px; background: #111827; border: 1px solid #1f2937; }
.kpi-title { font-size: 0.9rem; color: #9ca3af; margin-bottom: 8px; }
.kpi-value { font-size: 1.2rem; font-weight: 700; color: #e5e7eb; }
.section-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 8px; }
hr.soft { border: none; height: 1px; background: #1f2937; margin: 16px 0; }
</style>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────────
# 헤더
# ────────────────────────────────────────────────────────────────
st.title("🧰 주요 기능")
st.caption("대시보드의 핵심 기능을 요약하고, 작은 데모/샘플과 함께 확인할 수 있는 페이지입니다.")

# ────────────────────────────────────────────────────────────────
# 요약 카드
# ────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.markdown("<div class='kpi-card'><div class='kpi-title'>1–2사분면</div><div class='kpi-value'>지도·단지선택</div></div>", unsafe_allow_html=True)
with c2:
    st.markdown("<div class='kpi-card'><div class='kpi-title'>3사분면</div><div class='kpi-value'>혼잡도 시각화</div></div>", unsafe_allow_html=True)
with c3:
    st.markdown("<div class='kpi-card'><div class='kpi-title'>3-3/3-4</div><div class='kpi-value'>추세·시나리오</div></div>", unsafe_allow_html=True)
with c4:
    st.markdown("<div class='kpi-card'><div class='kpi-title'>4사분면</div><div class='kpi-value'>경제성·리포트</div></div>", unsafe_allow_html=True)
with c5:
    st.markdown("<div class='kpi-card'><div class='kpi-title'>사이드바</div><div class='kpi-value'>프리셋·가이드</div></div>", unsafe_allow_html=True)

st.divider()

# ────────────────────────────────────────────────────────────────
# 3️⃣ 주요 기능 (탭)
# ────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "1–2사분면: 지도·단지선택",
    "3사분면: 혼잡도 변화",
    "3-3: 추세 vs 재건축후(추정)",
    "3-4: 경제성/KPI",
    "사이드바: 프리셋/가이드",
    "기타 기능(자동화/통합)"
])

# ----------------------------------------------------------------
# 탭 1 — 1–2사분면: 지도 기반 단지 선택 및 속도 데이터 매핑
# ----------------------------------------------------------------
with tab1:
    st.markdown("### 🗺 1–2사분면: 지도 기반 단지 선택 및 속도 데이터 매핑")
    st.markdown("""
- **정비사업 목록**을 필터/정렬하고, 지도에서 **지점 선택**  
- 좌표 부재 시 **구(區) 중심 + Jitter**로 임시 표시  
- 선택된 단지 기준 반경 내 **링크 속도 데이터** 매핑
    """)
    st.code("""
# app.py 발췌
coords = load_coords().query("gu == @selected_gu")
df_map = projects_by_gu(selected_gu).merge(
    coords[["name","gu","lat","lon","full_address"]],
    on=["name","gu"], how="left"
)
# 좌표 누락 → 구 중심 + jitter
""", language="python")
    st.info("지도의 GeoJSON은 캐시에 보관하고, 세션에는 **키**만 저장해 메모리를 절감합니다.")

# ----------------------------------------------------------------
# 탭 2 — 3사분면: 혼잡도 변화 시각화
# ----------------------------------------------------------------
with tab2:
    st.markdown("### 📈 3사분면: 혼잡도 변화 (Altair)")
    st.markdown("""
- 링크별 속도를 **자유주행 대비 혼잡도(%)**로 변환  
- Top-N 링크의 **시간대별 라인 차트** 제공  
- 25–75 분위수 **밴드 시각화**로 변동성 표현
    """)
    st.code(r"""
# 속도→혼잡도 변환식(요약)
혼잡도_{l,h}[%] = ( 1 - min(1, v_{l,h} / v_ff,l) ) × 100
""", language="text")
    st.caption("Altair를 사용해 인터랙티브 툴팁/범례 제공")

# ----------------------------------------------------------------
# 탭 3 — 3-3: 추세 vs 재건축후(추정)
# ----------------------------------------------------------------
with tab3:
    st.markdown("### 📉 3-3: 기준 추세 vs 재건축 후(추정)")
    st.markdown("""
- 시간대별 평균 혼잡도 **다항회귀(≤3차)**로 기준 곡선 근사  
- 계획/기존 세대수 비율 `r`과 구별 민감도 `η`, 시간대 가중치 `w(h)` 반영  
- **새벽 완급**(시그모이드)로 비현실적 급변 방지
    """)
    st.code(r"""
# after(h) = 100 × [ 1 - (1 - base(h)/100) / (1 + η·ŵ(h)·(r-1)) ]
# ŵ(h): dawn smoothing 반영된 시간대 가중치
""", language="text")
    with st.expander("🔎 세션 상태에서 곡선이 있으면 미리 보기"):
        curve = st.session_state.get("curve_33")
        if isinstance(curve, pd.DataFrame) and set(["hour","base","after"]).issubset(curve.columns):
            st.line_chart(curve.set_index("hour")[["base","after"]])
        else:
            st.caption("곡선 데이터가 아직 없어요. 메인 대시보드(3-3)에서 생성됩니다.")

# ----------------------------------------------------------------
# 탭 4 — 3-4: 경제성 및 리포트 출력 (미니 데모)
# ----------------------------------------------------------------
with tab4:
    st.markdown("### 💰 3-4: 경제성 KPI (미니 데모)")
    st.markdown("아래 입력으로 **분양면적/매출/사업비/NPV/회수기간**을 간단 계산합니다. (메인과 동일 논리 요약본)")

    # 간단 KPI 계산기 (메인 app.py 로직 축약)
    def calc_kpis(households:int, avg_py:float, sale_price_per_m2:float, build_cost_per_m2:float,
                  infra_invest_bil:float, congestion_base:float, bus_inc_pct:int,
                  non_sale_ratio:float=0.15, sale_rate:float=0.98, disc_rate:float=0.07, years:int=4):
        m2_per_py = 3.3058
        avg_m2 = avg_py * m2_per_py
        sellable_m2 = households * avg_m2 * (1 - non_sale_ratio)
        predicted_cong = max(0.0, congestion_base * (1 - bus_inc_pct / 150))
        cong_improve = max(0.0, congestion_base - predicted_cong)

        revenue_won = sellable_m2 * sale_price_per_m2 * sale_rate
        cost_won = sellable_m2 * build_cost_per_m2
        total_cost_bil = cost_won/1e4/100 + infra_invest_bil
        total_rev_bil  = revenue_won/1e4/100

        profit_bil = total_rev_bil - total_cost_bil
        margin_pct = (profit_bil / total_cost_bil * 100) if total_cost_bil>0 else 0

        cf_annual = profit_bil / years if years>0 else profit_bil
        npv = sum([cf_annual / ((1+disc_rate)**t) for t in range(1, years+1)]) if years>0 else profit_bil
        payback = min(years, max(1, int(np.ceil(total_cost_bil / max(1e-6, cf_annual))))) if years>0 else 1

        return {
            "분양면적(㎡)": round(sellable_m2, 1),
            "예상혼잡도(%)": round(predicted_cong,1),
            "혼잡도개선(Δ%)": round(cong_improve,1),
            "총매출(억원)": round(total_rev_bil,1),
            "총사업비(억원)": round(total_cost_bil,1),
            "이익(억원)": round(profit_bil,1),
            "마진율(%)": round(margin_pct,1),
            "NPV(억원)": round(npv,1),
            "회수기간(년)": int(payback),
        }

    l, r = st.columns(2)
    with l:
        households = st.number_input("계획 세대수", 100, 20000, 1000, 50)
        avg_py = st.number_input("평균 전용면적(평)", 10.0, 70.0, 25.0, 0.5)
        sale_price = st.number_input("분양가(만원/㎡)", 500.0, 3000.0, 1200.0, 10.0)
        cost = st.number_input("공사비(만원/㎡)", 300.0, 2500.0, 900.0, 10.0)
        infra = st.number_input("인프라 투자(억원)", 0.0, 2000.0, 30.0, 5.0)
    with r:
        base_cong = st.slider("기준 혼잡도(%)", 0, 100, 50, 1)
        bus = st.slider("버스 증편(%)", 0, 100, 10, 5)
        non_sale = st.slider("비분양 비율", 0.0, 0.4, 0.15, 0.01)
        sale_rate = st.slider("분양률", 0.80, 1.00, 0.98, 0.01)
        disc = st.slider("할인율(재무)", 0.03, 0.15, 0.07, 0.005)
        years = st.slider("회수기간(년)", 2, 10, 4, 1)

    res = calc_kpis(households, avg_py, sale_price, cost, infra, base_cong, bus,
                    non_sale_ratio=non_sale, sale_rate=sale_rate, disc_rate=disc, years=years)

    st.markdown("#### 📊 산출 요약")
    df_res = pd.DataFrame([res]).T.rename(columns={0: "값"})
    st.dataframe(df_res, use_container_width=True)

    st.code("""
# 보고서/리포트 출력 팁
st.dataframe(df_result)
st.download_button("CSV로 내보내기", df_result.to_csv(index=False).encode("utf-8-sig"), "result.csv")
# PNG/Markdown/PDF는 charts 저장 또는 외부 패키지 활용
""", language="python")

# ----------------------------------------------------------------
# 탭 5 — 사이드바: 프리셋/가이드 시스템
# ----------------------------------------------------------------
with tab5:
    st.markdown("### 🧭 사이드바: 프리셋/가이드")
    st.markdown("""
- **프리셋 적용**: 데모 파라미터를 한번에 주입  
- **4사분면 가이드**: 해석 팁, 권장 입력 범위, 주의사항 제공  
- **캐시 비우기** 버튼: 데이터/리소스 캐시 초기화
    """)
    st.code("""
with st.sidebar:
    if st.button("캐시 비우기"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.session_state["matched_geo_key_daily"] = None
        st.rerun()
""", language="python")
    st.caption("프리셋/가이드는 `components/` 하위 모듈로 분리되어 유지보수 용이.")

# ----------------------------------------------------------------
# 탭 6 — 기타 기능: 자동 인코딩/CSV 변환/통합
# ----------------------------------------------------------------
with tab6:
    st.markdown("### 🧩 기타 기능: 자동화 & 통합")
    items = [
        ("🔤 Shapefile/CSV 인코딩 자동 감지", "smart_read_csv()로 cp949/euc-kr/utf-8-sig 등 순차 시도"),
        ("🧪 XLSX→CSV 자동 변환", "utils.traffic_preproc.ensure_speed_csv() 호출"),
        ("🧭 GeoJSON 캐시 키 전략", "세션에는 키만, 실제 GeoJSON은 캐시(dict store)에 보관"),
        ("🚦 교통량/속도 통합", "속도 기반 혼잡도 + (선택) 볼륨 데이터 추가 집계용 훅"),
        ("🧮 dtype 최적화", "_downcast_numeric/_categorify로 메모리 사용량 절감"),
    ]
    df_items = pd.DataFrame(items, columns=["기능", "설명"])
    st.table(df_items)

st.divider()
st.success("끝! — 주요 기능과 사용법을 빠르게 훑어볼 수 있는 안내 페이지입니다. 메인 대시보드(app.py)와 함께 사용하세요.")
