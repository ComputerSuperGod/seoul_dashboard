import streamlit as st
from pathlib import Path

# ------------------------------------------------------------------
# 📘 발표 정리 페이지 (pages/6_정리.py)
# - 대시보드 개요, 폴더 구조, 데이터셋, 파이프라인,
#   4사분면 로직 요약, 데모 시나리오, 향후 계획까지 한 페이지 요약
# ------------------------------------------------------------------

st.set_page_config(page_title="🧭 발표 정리 | AIoT 스마트 인프라 대시보드", layout="wide")
st.title("🧭 발표 정리 (Overview & Script)")
st.caption("대시보드 목적 · 구조 · 데이터 흐름 · 4사분면 요약 · 데모 스크립트 · 향후 계획")

# ---- 스타일 (가벼운 다크계열 카드)
st.markdown(
    """
    <style>
    .small-muted { color:#9ca3af; font-size:0.9rem; }
    .kpi-card { padding: 14px; border-radius: 14px; background: #111827; border: 1px solid #1f2937; }
    .kpi-title { font-size: 0.9rem; color: #9ca3af; margin-bottom: 8px; }
    .kpi-value { font-size: 1.2rem; font-weight: 700; color: #e5e7eb; }
    hr.soft { border: none; height: 1px; background: #1f2937; margin: 16px 0; }
    pre, code { font-size: 0.95rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ===== 0) 엘리베이터 피치 =====
with st.container(border=True):
    st.subheader("📌 한 줄 요약 (Elevator Pitch)")
    st.markdown(
        """
        **AIoT 데이터를 결합**해 **재건축 후보지의 교통혼잡·사업성**을 
        **한 눈에 비교/설명**하는 **의사결정 보조 대시보드**입니다.
        - 지도 기반 후보지 선택 → 교통·KPI 산출 → **시나리오/민감도/확률** 분석 → **자동 리포트**.
        """
    )

st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

# ===== 1) 폴더 구조 =====
with st.container(border=True):
    st.subheader("📁 프로젝트 구조")
    colL, colR = st.columns([1.3, 1])
    with colL:
        st.markdown(
            """
            ```
            📦 app/
            ┣ 📜 app.py
            ┣ 📁 components/
            │  ┣ sidebar_4quadrant_guide.py
            │  ┗ sidebar_presets.py
            ┣ 📁 pages/
            │  ┣ 1_FAQ.py
            │  ┣ 2_재건축이란.py
            │  ┣ 3_재건축_참여_가이드.py
            │  ┣ 4_4사분면 설명(탭 및 로직).py
            │  ┣ 5_4사분면 설명(공식).py
            │  ┗ 6_정리.py   ← (본 페이지)
            ┣ 📁 data/
            │  ┣ AverageSpeed_Seoul_2023.csv
            │  ┣ AverageSpeed(LINK).xlsx
            │  ┣ TrafficVolume(LINK).xlsx
            │  ┣ seoul_redev_projects.csv
            │  ┗ seoul_link_lev5.5_2023.(shp/dbf/shx/prj)
            ┗ 📁 utils/
               ┣ traffic_preproc.py
               ┗ traffic_plot.py
            ```
            """
        )
    with colR:
        st.markdown(
            """
            **핵심 포인트**
            - `pages/` : 발표·교육용 콘텐츠 포함(개념/가이드/공식/정리)
            - `components/` : 사이드바 가이드 + 프리셋(데모 즉시 가능)
            - `data/` : 후보지·속도·교통량·도로망(GIS) 실데이터
            - `utils/` : 엑셀→CSV 표준화, 반경내 속도차트 유틸
            """
        )

st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

# ===== 2) 데이터셋 =====
with st.container(border=True):
    st.subheader("🧮 데이터 자원 (Datasets)")
    st.markdown(
        """
        - **재건축 후보지**: `seoul_redev_projects.csv` (자치구·세대수·면적 등)
        - **교통속도**: `AverageSpeed_Seoul_2023.csv` / `AverageSpeed(LINK).xlsx`
        - **교통량(선택)**: `TrafficVolume(LINK).xlsx`
        - **도로망 GIS**: `seoul_link_lev5.5_2023.shp` (+ `.dbf/.shx/.prj`)
        - **좌표 매칭 보조**: `서울시_재개발재건축_clean_kakao.csv`
        """
    )

st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

# ===== 3) 데이터 파이프라인 =====
with st.container(border=True):
    st.subheader("🔄 데이터 흐름 (Pipeline)")
    col1, col2 = st.columns([1.1, 1])
    with col1:
        st.markdown(
            """
            1) **원천**  
               후보지 CSV · 속도/교통량 Excel/CSV · 도로망 SHP

            2) **전처리**  
               - Excel → CSV 자동 변환 (시간대 `0~1시` 탐지, `hour` 생성)  
               - 링크ID 표준화(`link_id`), 좌표계 변환(EPSG:4326/3857)

            3) **분석/시각화**  
               - 반경 내 링크 속도 트렌드  
               - 혼잡도·KPI 산출  
               - 지도(pydeck) + 차트(Altair)
            """
        )
    with col2:
        st.markdown(
            """
            ```text
            [CSV/Excel/SHP]
                 ↓ 전처리(utils)
            [표준화 Long CSV]
                 ↓ 분석
            [혼잡도·KPI]
                 ↓ 시각화
            [지도 + 차트 + 리포트]
            ```
            """
        )

st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

# ===== 4) 4사분면 요약 =====
with st.container(border=True):
    st.subheader("🧭 4사분면 요약 (입력 → 분석 → 인사이트)")
    tab1, tab2, tab3, tab4 = st.tabs(["🧩 시나리오", "📈 민감도", "🎲 확률(간이)", "📤 리포트"])

    with tab1:
        st.markdown(
            """
            **입력**: 세대수, 평균 전용면적(평), 분양가(만원/㎡), 공사비(만원/㎡),  
            버스 증편률(%), 인프라 투자비(억원), 분양률, 할인율, 회수기간

            **출력**: 매출·공사비·총이익(억), 마진율(%), 혼잡도 개선율(%)  
            **의미**: 시나리오 A/B/C의 **사업성·교통효과**를 빠르게 비교
            """
        )
    with tab2:
        st.markdown(
            """
            **입력**: (기준값 대비) 분양가·공사비·버스증편·인프라비의 ±변동(%)  
            **출력**: ΔNPV 토네이도 차트  
            **의미**: 수익성에 **영향이 큰 변수**와 리스크 요인을 식별
            """
        )
    with tab3:
        st.markdown(
            """
            **입력**: 분양가·공사비의 평균·분산, 반복횟수(예: 500~1000회)  
            **출력**: NPV 확률분포 및 P10/P50/P90  
            **의미**: 불확실성 범위를 수치로 제시하여 보수/기준/낙관 시나리오 파악
            """
        )
    with tab4:
        st.markdown(
            """
            **입력**: 각 탭의 결과 요약  
            **출력**: 표·차트 요약 + 자동 해석 텍스트 + CSV/PDF 내보내기  
            **의미**: 의사결정 보고서로 곧바로 활용
            """
        )

st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

# ===== 5) 데모 스크립트 =====
with st.container(border=True):
    st.subheader("🎬 데모 진행 스크립트 (3~4분)")
    st.markdown(
        """
        1. **구 선택**: 사이드바에서 관심 구를 선택 → 지도와 리스트가 갱신됩니다.
        2. **후보 단지 선택**: 리스트에서 1곳 체크 → 지도 툴팁/정보 확인.
        3. **프리셋 적용**: `🧪 4사분면 예시값(프리셋)`에서 **기준(Base)** 적용.
        4. **시나리오 탭**: A/B/C 입력(분양가·공사비·버스·인프라) 비교 → KPI 하이라이트.
        5. **민감도 탭**: ±변동폭 조정 → ΔNPV 막대 길이로 **핵심 변수** 강조.
        6. **확률 탭**: 반복수 500~1000 → P10/P50/P90로 **리스크 범위** 설명.
        7. **리포트 탭**: 체크리스트/요약 텍스트 확인 → **CSV/PDF**로 내보내기.
        """
    )

st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

# ===== 6) 핵심 메시지 & 청중별 포인트 =====
with st.container(border=True):
    st.subheader("🗣️ 핵심 메시지 & 청중별 포인트")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            """
            **건설사/조합**
            - 데이터 기반 제안서: **교통개선 ↔ 수익성**을 함께 제시
            - 시나리오/민감도/확률로 **리스크 관리**
            """
        )
    with c2:
        st.markdown(
            """
            **지자체/심의기관**
            - 근거 데이터와 **개선 시나리오**로 협의 지연 방지
            - KPI로 **정책 효과**를 수치화
            """
        )
    with c3:
        st.markdown(
            """
            **내부 경영진**
            - 투자집행 전 **민감 변수** 확인
            - **NPV/PB** 기반 빠른 의사결정
            """
        )

st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

# ===== 7) (부록) 핵심 수식 스니펫 =====
with st.container(border=True):
    st.subheader("🧮 부록: 핵심 수식")
    st.latex(r"\text{1평} = 3.3058\,\text{m}^2")
    st.latex(
        r"A_{\text{sellable}} = N_{\text{households}}\times A_{\text{avg,py}}\times 3.3058\times (1 - R_{\text{non-sale}})")
    st.latex(
        r"C_{\text{pred}} = \max\left(0,\; C_{\text{base}}\times\left(1 - \frac{R_{\text{bus}}}{150}\right)\right)")
    st.latex(r"\Pi = R_{\text{bil}} - C_{\text{bil}},\quad M = \frac{\Pi}{C_{\text{bil}}}\times 100")
    st.latex(
        r"NPV = \sum_{t=1}^{Y} \frac{CF_{\text{annual}}}{(1+r)^t},\quad \text{Payback} = \left\lceil \frac{C_{\text{bil}}}{CF_{\text{annual}}} \right\rceil")

st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

# ===== 8) 다운로드 (발표용 텍스트) =====
with st.container(border=True):
    st.subheader("⬇️ 발표 대본 텍스트 다운로드")

    script_md = """
# 발표 대본 (요약)

## 한 줄 요약
AIoT 데이터를 결합해 재건축 후보지의 교통혼잡·사업성을 한 눈에 비교/설명하는 의사결정 보조 대시보드.

## 프로젝트 구조
- pages(FAQ/개념/가이드/4사분면/정리), components(가이드/프리셋), data(속도·교통량·도로망), utils(전처리/시각화)

## 데이터 흐름
원천데이터 → 전처리(Excel→CSV, 링크ID 표준화) → 혼잡도·KPI → 지도+차트 → 리포트

## 4사분면 요약
- 시나리오: A/B/C 사업성·혼잡도 비교
- 민감도: ΔNPV 토네이도로 핵심 변수 파악
- 확률: P10/P50/P90로 불확실성 제시
- 리포트: 자동 요약 및 내보내기

## 데모 스크립트(핵심)
구 선택 → 단지 선택 → 프리셋 적용 → 시나리오 비교 → 민감도/확률 → 리포트

## 핵심 메시지
교통개선과 수익성을 동시에 정량화하여 설득력 있는 의사결정을 지원.
"""

    st.download_button(
        label="발표 대본(.md) 다운로드",
        data=script_md,
        file_name="presentation_script.md",
        mime="text/markdown",
    )

st.caption("© AIoT 스마트 인프라 대시보드 — 발표용 요약 페이지")
