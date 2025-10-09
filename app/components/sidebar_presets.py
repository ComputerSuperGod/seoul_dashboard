# app/components/sidebar_presets.py
import streamlit as st

# 대시보드에서 쓰는 입력키를 한 곳에서 정의
COMMON_KEYS = [
    "households", "desired_py", "congestion_base", "non_sale_ratio",
    "sale_rate", "disc_rate", "years", "base_bus_inc"
]
SCEN_KEYS = ["sale_A","cost_A","bus_A","infra_A",
             "sale_B","cost_B","bus_B","infra_B",
             "sale_C","cost_C","bus_C","infra_C"]

# 3가지 프리셋 정의 (범위: 코드의 number_input/slider 제한 내)
PRESETS = {
    "보수적(Conservative)": {
        # 공통 입력
        "households": 800,
        "desired_py": 24.0,          # 평균 전용(평)
        "congestion_base": 55.0,     # 기준 혼잡도(%)
        "non_sale_ratio": 0.18,
        "sale_rate": 0.95,
        "disc_rate": 0.09,
        "years": 6,
        "base_bus_inc": 5,

        # 시나리오 A/B/C
        "sale_A": 1100.0, "cost_A": 950.0, "bus_A": 10, "infra_A": 40.0,
        "sale_B": 1150.0, "cost_B":1000.0, "bus_B": 15, "infra_B": 60.0,
        "sale_C": 1050.0, "cost_C": 900.0, "bus_C":  5, "infra_C": 30.0,
    },
    "기준(Base)": {
        "households": 1200,
        "desired_py": 25.0,
        "congestion_base": 50.0,
        "non_sale_ratio": 0.15,
        "sale_rate": 0.98,
        "disc_rate": 0.07,
        "years": 4,
        "base_bus_inc": 15,

        "sale_A": 1200.0, "cost_A": 900.0, "bus_A": 15, "infra_A": 30.0,
        "sale_B": 1300.0, "cost_B": 950.0, "bus_B": 25, "infra_B": 50.0,
        "sale_C": 1100.0, "cost_C": 850.0, "bus_C": 10, "infra_C": 20.0,
    },
    "공격적(Aggressive)": {
        "households": 1500,
        "desired_py": 27.0,
        "congestion_base": 60.0,
        "non_sale_ratio": 0.12,
        "sale_rate": 0.99,
        "disc_rate": 0.06,
        "years": 3,
        "base_bus_inc": 25,

        "sale_A": 1350.0, "cost_A": 920.0, "bus_A": 25, "infra_A": 40.0,
        "sale_B": 1450.0, "cost_B": 980.0, "bus_B": 35, "infra_B": 60.0,
        "sale_C": 1250.0, "cost_C": 880.0, "bus_C": 20, "infra_C": 25.0,
    },
}

def _apply_preset(values: dict):
    """세션 상태에 프리셋 값 주입"""
    for k, v in values.items():
        st.session_state[k] = v

def _show_preview(values: dict):
    """간단 미리보기 (사이드바 표기용)"""
    st.caption("선택한 예시값 미리보기")
    st.write(
        f"- 세대수: **{values['households']:,}** / 평균전용: **{values['desired_py']}평**\n"
        f"- 기준혼잡도: **{values['congestion_base']}%** / 비분양: **{int(values['non_sale_ratio']*100)}%**\n"
        f"- 분양률: **{int(values['sale_rate']*100)}%** / 할인율: **{values['disc_rate']*100:.1f}%** / 회수기간: **{values['years']}년**\n"
        f"- 베이스 버스증편: **{values['base_bus_inc']}%**\n"
        f"- 시나리오 A: 분양가 {values['sale_A']} / 공사비 {values['cost_A']} / 버스 {values['bus_A']}% / 인프라 {values['infra_A']}억원\n"
        f"- 시나리오 B: 분양가 {values['sale_B']} / 공사비 {values['cost_B']} / 버스 {values['bus_B']}% / 인프라 {values['infra_B']}억원\n"
        f"- 시나리오 C: 분양가 {values['sale_C']} / 공사비 {values['cost_C']} / 버스 {values['bus_C']}% / 인프라 {values['infra_C']}억원"
    )

def render_sidebar_presets():
    """사이드바: 예시값(프리셋) 선택 UI"""
    with st.sidebar.expander("🧪 4사분면 예시값(프리셋)"):
        choice = st.radio(
            "데모/교육용으로 준비된 예시값을 선택하세요.",
            options=list(PRESETS.keys()),
            index=1,   # 기본: '기준(Base)'
            help="선택 후 '예시값 적용'을 누르면 4사분면 탭의 입력값들이 자동으로 채워집니다."
        )
        values = PRESETS[choice]
        _show_preview(values)

        col1, col2 = st.columns([1,1])
        with col1:
            if st.button("✅ 예시값 적용"):
                _apply_preset(values)
                st.success(f"‘{choice}’ 프리셋을 적용했습니다. 4사분면 탭에서 바로 확인하세요.")
        with col2:
            if st.button("↩️ 기본값 초기화"):
                # 현재 프리셋을 기준으로 초기화하되, 원하는 경우 완전 초기화 로직으로 교체 가능
                for k in COMMON_KEYS + SCEN_KEYS:
                    if k in st.session_state:
                        del st.session_state[k]
                st.info("세션 기본값을 초기화했습니다.")
