# pages/6_데이터 흐름 및 분석 로직.py
# 🔄 AIoT 스마트 인프라 대시보드 — 데이터 흐름 & 분석 로직 개요

from __future__ import annotations
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np

# (선택) 내부 유틸 임포트 — 존재하지 않으면 안내만 표시
HAS_PREPROC = HAS_PLOT = False
try:
    from utils.traffic_preproc import ensure_speed_csv, convert_average_speed_excel_to_csv
    HAS_PREPROC = True
except Exception:
    pass

try:
    # plot_speed가 있으면 통합 진입점으로 사용
    from utils.traffic_plot import plot_speed
    HAS_PLOT = True
except Exception:
    plot_speed = None

# ────────────────────────────────────────────────────────────────
# 공통 스타일
# ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="데이터 흐름 & 분석 로직 | AIoT 스마트 인프라 대시보드", layout="wide")
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
code { font-size: 0.9rem !important; }
</style>
""", unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────────
# 헤더 & 요약 카드
# ────────────────────────────────────────────────────────────────
st.title("🔄 데이터 흐름 & 분석 로직")
st.caption("엑셀→CSV 전처리 → 반경 내 링크 추출 → 속도→혼잡도 변환 → 일평균/시간대 분석 → 시나리오 KPI 계산까지의 전체 파이프라인을 정리합니다.")

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown("<div class='kpi-card'><div class='kpi-title'>전처리</div><div class='kpi-value'>엑셀→CSV 변환</div></div>", unsafe_allow_html=True)
with c2:
    st.markdown("<div class='kpi-card'><div class='kpi-title'>링크 선택</div><div class='kpi-value'>반경 필터링</div></div>", unsafe_allow_html=True)
with c3:
    st.markdown("<div class='kpi-card'><div class='kpi-title'>혼잡도</div><div class='kpi-value'>속도→% 변환</div></div>", unsafe_allow_html=True)
with c4:
    st.markdown("<div class='kpi-card'><div class='kpi-title'>시나리오</div><div class='kpi-value'>KPI/민감도</div></div>", unsafe_allow_html=True)

st.divider()

# ────────────────────────────────────────────────────────────────
# 파이프라인 다이어그램
# ────────────────────────────────────────────────────────────────
st.subheader("📈 데이터 파이프라인(Flow Diagram)")
st.graphviz_chart("""
digraph G {
    rankdir=LR;
    node [shape=rectangle, style="rounded,filled", fillcolor="#0b1220", color="#1f2937", fontcolor="white"];
    edge [color="#6b7280"];

    subgraph cluster_src {
        label="입력 데이터";
        style="rounded";
        color="#1f2937";
        xlsx [label="AverageSpeed(LINK).xlsx"];
        shp  [label="seoul_link_lev5.5_2023.shp"];
        proj [label="seoul_redev_projects.csv"];
        geo  [label="서울시_재개발재건축_clean_kakao.csv"];
    }

    pre [label="traffic_preproc.py\\n• convert_average_speed_excel_to_csv()\\n• ensure_speed_csv()", fillcolor="#111827"];
    csv [label="AverageSpeed(LINK)_YYYY.csv"];

    plot [label="traffic_plot.py\\n• plot_speed() (Altair/Matplotlib/Plotly)\\n• 반경 내 링크 추출 & 시간대 집계", fillcolor="#111827"];

    cong [label="속도→혼잡도 변환\\nfree_flow 대비 혼잡%(0~100)", fillcolor="#111827"];
    daily [label="일평균/Top-N/분위수 밴드", fillcolor="#111827"];

    model [label="3-3 추세 vs 재건축후(추정)\\nr, η, w(h) 반영", fillcolor="#111827"];
    kpi [label="3-4 KPI/민감도/확률", fillcolor="#111827"];

    xlsx -> pre -> csv -> plot;
    shp -> plot;
    proj -> plot;
    geo -> plot;

    plot -> cong -> daily -> model -> kpi;
}
""")

st.caption("※ 실제 렌더는 app.py에서 수행. 이 페이지는 아키텍처/흐름을 문서화하고, 간단한 데모/검증 도구를 제공합니다.")

st.divider()

# ────────────────────────────────────────────────────────────────
# 탭 구성: 전처리 / 플로팅 / 변환식 / 엔드투엔드 / 트러블슈팅
# ────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "엑셀→CSV 전처리 (traffic_preproc.py)",
    "반경 필터·시각화 (traffic_plot.py)",
    "속도→혼잡도 변환식",
    "엔드투엔드(샘플 실행)",
    "트러블슈팅 체크리스트"
])

# ----------------------------------------------------------------
# 탭1 — 전처리
# ----------------------------------------------------------------
with tab1:
    st.markdown("### 🧹 엑셀→CSV 전처리 (`traffic_preproc.py`)")
    st.markdown("""
- **`convert_average_speed_excel_to_csv(xlsx_path, csv_path)`**  
  • AverageSpeed 형식 엑셀을 CSV로 저장  
  • **시간대 헤더 자동 탐지**(예: `h0..h23`, `0시..23시` 등 혼합 케이스)  
  • **`link_id` 표준화**: 문자열화 + 공백 제거 + `.0` 제거  
- **`ensure_speed_csv(xlsx_in, csv_out)`**  
  • CSV가 없고 엑셀이 있으면 **자동 변환**  
  • 캐시/파일상태 확인 후 **중복 변환 방지**
    """)
    st.code("""
# 사용 예시
from utils.traffic_preproc import ensure_speed_csv
ensure_speed_csv(Path('data/AverageSpeed(LINK).xlsx'), Path('data/AverageSpeed(LINK)_2023.csv'))
""", language="python")

    if not HAS_PREPROC:
        st.warning("utils.traffic_preproc 모듈을 찾지 못했습니다. (문서용 안내만 표시 중)")
    else:
        with st.expander("간이 실행(선택)"):
            x1, x2 = st.columns(2)
            with x1:
                xlsx_p = st.text_input("엑셀 경로", "data/AverageSpeed(LINK).xlsx")
            with x2:
                csv_p  = st.text_input("CSV 저장 경로", "data/AverageSpeed(LINK)_2023.csv")
            if st.button("ensure_speed_csv 실행", type="primary"):
                try:
                    ensure_speed_csv(Path(xlsx_p), Path(csv_p))
                    st.success(f"완료: {csv_p}")
                except Exception as e:
                    st.error(f"실패: {e}")

# ----------------------------------------------------------------
# 탭2 — plotting
# ----------------------------------------------------------------
with tab2:
    st.markdown("### 🗺 반경 필터·시각화 (`traffic_plot.py`)")
    st.markdown("""
- **`plot_speed(csv_path, shp_path, center_lon, center_lat, radius_m, max_links, renderer)`**  
  • Shapefile의 링크를 중심점/반경으로 **공간 필터링**  
  • CSV 속도 데이터에서 해당 링크의 시간대별 속도 추출  
  • **Altair/Matplotlib/Plotly** 중 선택 렌더  
  • 반환: `(chart, df_plot)` — 차트(옵션)와 **정규화된 속도 테이블**
    """)
    st.code("""
# 단독 실행 예시 (Altair)
from utils.traffic_plot import plot_speed
chart, df_plot = plot_speed(
    csv_path='data/AverageSpeed(LINK)_2023.csv',
    shp_path='data/seoul_link_lev5.5_2023.shp',
    center_lon=127.0473, center_lat=37.5172,  # 강남구청 근방
    radius_m=1000, max_links=10, renderer='altair', chart_height=300
)
""", language="python")

    if not HAS_PLOT:
        st.info("utils.traffic_plot 모듈을 찾지 못했습니다. (app.py에서는 존재 가정)")

# ----------------------------------------------------------------
# 탭3 — 속도→혼잡도 변환
# ----------------------------------------------------------------
with tab3:
    st.markdown("### 🚦 속도→혼잡도(%) 변환식")
    st.markdown("""
- 링크 `l`의 **자유주행속도** `v_ff,l = max_h v_{l,h}`  
- 시간대 `h`에서의 혼잡도:
    """)
    st.latex(r"\mathrm{Congestion}_{l,h}(\%)=\left(1-\min\left(1,\frac{v_{l,h}}{v_{\mathrm{ff},l}}\right)\right)\times 100")
    st.markdown("""
- 의미: **0% = 자유주행**, **100% = 매우 혼잡**  
- 실제 구현은 `app.py`의 `compute_congestion_from_speed()` 참고
    """)
    st.code("""
def compute_congestion_from_speed(df_plot: pd.DataFrame) -> pd.DataFrame:
    d = df_plot.copy()
    d["평균속도(km/h)"] = pd.to_numeric(d["평균속도(km/h)"], errors="coerce")
    d["free_flow"] = d.groupby("link_id")["평균속도(km/h)"].transform("max").clip(lower=1)
    d["value"] = ((1 - (d["평균속도(km/h)"] / d["free_flow"]).clip(0, 1)) * 100).clip(0, 100)
    return d[["link_id","hour","value"]]
""", language="python")

# ----------------------------------------------------------------
# 탭4 — 엔드투엔드(샘플 실행)
# ----------------------------------------------------------------
with tab4:
    st.markdown("### ▶️ 엔드투엔드(샘플) — 가능 시 간단 실행")
    st.caption("※ 실제 대시보드(app.py)에서는 지도/차트/시나리오와 연결됩니다. 여기서는 핵심 흐름만 검증합니다.")

    csv_path = st.text_input("CSV 경로", "data/AverageSpeed(LINK)_2023.csv")
    shp_path = st.text_input("SHP 경로", "data/seoul_link_lev5.5_2023.shp")
    clat = st.number_input("center_lat", 30.0, 45.0, 37.5172, 0.0001)
    clon = st.number_input("center_lon", 120.0, 135.0, 127.0473, 0.0001)
    radius = st.slider("반경(m)", 300, 3000, 1000, 100)
    max_links = st.slider("Top-N 링크", 5, 50, 10, 1)

    can_run = HAS_PLOT and Path(csv_path).exists() and Path(shp_path).exists()
    if st.button("샘플 실행", type="primary", disabled=not can_run):
        try:
            chart, df_plot = plot_speed(
                csv_path=csv_path,
                shp_path=shp_path,
                center_lon=clon, center_lat=clat,
                radius_m=radius, max_links=max_links,
                renderer="altair", chart_height=280,
            )
            if chart is not None:
                st.altair_chart(chart, use_container_width=True, theme=None)

            # 혼잡도 변환 및 일평균 예시
            from math import isnan
            d = df_plot.copy()
            d["평균속도(km/h)"] = pd.to_numeric(d["평균속도(km/h)"], errors="coerce")
            d["free_flow"] = d.groupby("link_id")["평균속도(km/h)"].transform("max").clip(lower=1)
            d["혼잡도(%)"] = ((1 - (d["평균속도(km/h)"] / d["free_flow"]).clip(0, 1)) * 100).clip(0, 100)

            df_daily = d.groupby("link_id", as_index=False)["혼잡도(%)"].mean().rename(columns={"혼잡도(%)":"일평균 혼잡(%)"})
            st.markdown("#### 📊 일평균 혼잡(%) — 샘플")
            st.dataframe(df_daily.head(15), use_container_width=True)
        except Exception as e:
            st.error(f"실행 실패: {e}")
    if not can_run:
        st.info("모듈/파일이 확인되면 실행 버튼이 활성화됩니다. (utils.traffic_plot, CSV/SHP 경로)")

# ----------------------------------------------------------------
# 탭5 — 트러블슈팅
# ----------------------------------------------------------------
with tab5:
    st.markdown("### 🧯 트러블슈팅 체크리스트")
    problems = [
        ("CSV가 없어요", "data 폴더에 AverageSpeed(LINK).xlsx를 넣고, app.py 또는 이 페이지에서 ensure_speed_csv 실행"),
        ("Shapefile 좌표계 이슈", "gdf.crs가 EPSG:4326이 아니면 to_crs(4326)으로 변환"),
        ("링크ID 매칭 안 됨", "엑셀/CSV/Shape의 link_id를 문자열화 + .0 제거 + 공백 제거"),
        ("메모리/속도 저하", "st.cache_data/resource 사용, _downcast_numeric/_categorify로 dtype 최적화"),
        ("지도에 선 색상 안 보임", "GeoJsonLayer에서 get_line_width/line_width_min_pixels 지정했는지 확인"),
        ("그래프가 비어 있음", "반경이 너무 작거나 데이터 부재 — 반경 확대/연도/파일 경로 확인"),
    ]
    st.table(pd.DataFrame(problems, columns=["문제", "해결 가이드"]))
    st.caption("추가로, app.py의 `legend_slot`, `matched_geo_key_daily` 키 전략(세션=키/실데이터=캐시)을 준수하면 메모리 사용량을 크게 줄일 수 있습니다.")

st.divider()
st.success("완료 — 전처리부터 시각화·모형·KPI까지의 흐름을 문서화했습니다. 이 페이지는 운영/유지보수 가이드로 활용하세요.")
