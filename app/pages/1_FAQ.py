# app/pages/1_FAQ.py
# -------------------------------------------------------------
# 📘 FAQ 페이지
# -------------------------------------------------------------
import sys
from pathlib import Path

import streamlit as st

# --- ensure project root (app/) is importable for components/*
BASE_DIR = Path(__file__).resolve().parent.parent  # .../app
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# (선택) 공통 사이드바 네비: 없다면 주석 처리
try:
    from components.sidebar_nav import render_sidebar_nav
except Exception:
    render_sidebar_nav = None

st.set_page_config(page_title="FAQ | AIoT 스마트 인프라 대시보드", layout="wide")

# ---- Optional Global Style (가볍게)
st.markdown("""
<style>
.block-container { padding-top: 1.2rem; }
hr.soft { border: none; height: 1px; background: #1f2937; margin: 16px 0; }
.small-muted { color:#9ca3af; font-size:0.9rem; }
</style>
""", unsafe_allow_html=True)

# ---- Sidebar: Navigation + Search
with st.sidebar:
    if render_sidebar_nav:
        render_sidebar_nav(active="FAQ")
    st.markdown("### 🔎 FAQ 검색")
    q = st.text_input("키워드로 검색", value="", placeholder="예: 혼잡도, KPI, 인허가")

st.title("❓ FAQ (자주 묻는 질문)")
st.caption("대시보드의 목적, 지표 해석, 데이터 출처, 인허가/교통 대응 전략까지 한 눈에 정리했습니다.")

# ---- FAQ 데이터
FAQ = [
    {
        "section": "대시보드 개요",
        "q": "이 대시보드는 무엇을 위한 건가요?",
        "a": """AIoT 기반 **스마트 인프라 분석 시스템**으로, 재건축 사업에서 교통혼잡, 수익성,
        인허가 리스크 등을 사전에 예측·설명합니다. 건설사/조합/지자체가 **데이터 근거**로 의사결정하도록 돕습니다."""
    },
    {
        "section": "대시보드 개요",
        "q": "실제 데이터와 연결되나요?",
        "a": """현재는 서울시 공개자료와 샘플을 사용합니다. 운영 단계에선 도로망/버스노선/정비사업 API,
        민간 교통데이터 등으로 확장 가능합니다."""
    },
    {
        "section": "교통 혼잡도",
        "q": "혼잡도 지표는 왜 필요한가요?",
        "a": """법정 부담금 산정 자체에는 직접 포함되지 않아도, **교통영향평가·인허가 협의**에서
        리스크를 미리 드러내고 **개선안(버스 증설, 신호 최적화 등)**을 제시하는 데 핵심 근거가 됩니다."""
    },
    {
        "section": "교통 혼잡도",
        "q": "혼잡도가 높으면 사업이 불리해지나요?",
        "a": """단기적으로는 개선비 부담이 늘 수 있지만, **선제 개선계획**을 설계에 반영하면
        행정평가 리스크를 줄이고 **인허가 지연**을 방지할 수 있습니다."""
    },
    {
        "section": "교통 혼잡도",
        "q": "부담금/분담금으로 버스 증설이 가능한가요?",
        "a": """법정 산식은 각 제도별로 정해져 있지만, 지자체 협의 시 **교통개선 사업(예: 버스 증차, 정류장 개선)**을
        조건부로 패키징하는 사례가 있습니다. 대시보드는 어느 정도의 개선이 필요한지 **정량 가이드**를 제공합니다."""
    },
    {
        "section": "재건축 절차/역할",
        "q": "건설사는 언제 참여하고, 평형은 누가 정하나요?",
        "a": """통상 조합 설립 이후 시공사 선정 단계에서 참여합니다. 기본안은 조합/설계가 제시하지만,
        시공사는 **대안 평형 구성**을 제안할 수 있습니다. 대시보드에선 평형·세대수 시뮬레이션으로
        교통·수익에 미치는 효과를 즉시 확인합니다."""
    },
    {
        "section": "KPI",
        "q": "KPI에는 무엇이 포함되나요?",
        "a": """- 평균 혼잡도(%)  
- 총 기대 수익(십억 원)  
- 교통개선 필요 구간 수(추가 예정)  
- 잠재 민원 리스크 점수(추가 예정)  

KPI는 **설계/정책 가정의 변화가 결과에 미치는 영향**을 빠르게 피드백하기 위한 요약지표입니다."""
    },
    {
        "section": "데이터/방법론",
        "q": "어떤 데이터로 분석하나요?",
        "a": """- `seoul_redev_projects.csv`: 정비사업 위치/속성  
- `AverageSpeed_Seoul_2023.csv`: 링크별 시간대 평균속도  
- `seoul_link_lev5.5_2023.shp`: 도로망 지오메트리  
- (선택) `TrafficVolume_Seoul_2023.csv`: 차량 통행량"""
    },
    {
        "section": "데이터/방법론",
        "q": "혼잡도 색상 기준은요?",
        "a": """<30%: 초록(원활) · 30~70%: 노랑(보통) · ≥70%: 빨강(혼잡).  
지도에서는 링크별 일평균 혼잡도를 기반으로 선 색상을 부여합니다."""
    },
    {
        "section": "해석/활용",
        "q": "혼잡도를 법정 산정식에 굳이 넣을 필요가 있나요?",
        "a": """법정 산정식은 **그대로 준수**합니다. 혼잡도는 '협의·설득용 보조 지표'로 쓰입니다.
즉, **왜 이만큼의 교통개선이 필요한지**를 이해관계자에게 설명하고, 대안 시나리오 간 **우선순위**를 정하는 데 사용합니다."""
    },
]

# ---- 검색 필터
def match(item, qtxt: str) -> bool:
    if not qtxt:
        return True
    qtxt = qtxt.strip().lower()
    blob = f"{item['section']} {item['q']} {item['a']}".lower()
    return qtxt in blob

filtered = [f for f in FAQ if match(f, q)]
sections = []
for f in filtered:
    if f["section"] not in sections:
        sections.append(f["section"])

# ---- 렌더
for sec in sections:
    st.subheader(f"📂 {sec}")
    for f in [x for x in filtered if x["section"] == sec]:
        with st.expander(f"Q. {f['q']}", expanded=False):
            st.markdown(f["a"])
    st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

# ---- 하단: 도움말
st.markdown("#### 더 궁금한 점이 있나요?")
st.markdown(
    "<span class='small-muted'>사이드바의 “대시보드 홈” 또는 “사업성 분석”으로 이동해 "
    "실제 지표를 조정·시뮬레이션해 보세요.</span>",
    unsafe_allow_html=True
)
