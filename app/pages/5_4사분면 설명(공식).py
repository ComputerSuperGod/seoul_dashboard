import streamlit as st

def app():
    st.title("📘 4사분면 계산식 및 의미 설명")
    st.caption("AIoT 스마트 인프라 대시보드의 시나리오·재무·민감도·리포트 탭에서 사용된 모든 주요 공식과 그 의미를 정리했습니다.")
    st.markdown("---")

    # 1️⃣ 면적 계산
    st.header("① 면적 계산 (주택 규모 관련)")
    st.latex(r"""
    \text{1평} = 3.3058 \text{m}^2
    """)
    st.markdown("""
    평(坪)을 ㎡(제곱미터)로 변환하기 위한 기본 단위입니다.  
    한국 부동산의 면적 단위는 평으로 표시되지만, 재무 계산 및 공사비 산정은 국제 표준 단위(㎡)로 수행됩니다.
    """)

    st.latex(r"""
    A_{\text{sellable}} = N_{\text{households}} \times A_{\text{avg,py}} \times 3.3058 \times (1 - R_{\text{non-sale}})
    """)
    st.markdown("""
    - \( A_{\text{sellable}} \): 총 분양 가능 면적(㎡)  
    - \( N_{\text{households}} \): 세대수  
    - \( A_{\text{avg,py}} \): 평균 전용면적(평)  
    - \( R_{\text{non-sale}} \): 비분양 비율(공공·커뮤니티 공간 등)

    👉 즉, **세대 수 × 평균면적 × (1-비분양비율)** 로 분양 가능한 총 면적을 구합니다.
    """)

    # 2️⃣ 혼잡도 개선
    st.header("② 혼잡도 개선 모델 (교통효과)")
    st.latex(r"""
    C_{\text{pred}} = \max\left(0,\; C_{\text{base}} \times \left(1 - \frac{R_{\text{bus}}}{150}\right)\right)
    """)
    st.markdown("""
    - \( C_{\text{pred}} \): 버스 증편 후 예상 혼잡도(%)  
    - \( C_{\text{base}} \): 기준 혼잡도(%)  
    - \( R_{\text{bus}} \): 버스 증편률(%)  

    ⚙️ 버스를 150% 증편하면 혼잡도가 0%로 수렴하도록 단순 선형 근사한 식입니다.  
    즉, **버스 1%p 증편 → 혼잡도 약 0.67%p 개선 효과**로 설정되어 있습니다.
    """)

    st.latex(r"""
    \Delta C = \max(0,\; C_{\text{base}} - C_{\text{pred}})
    """)
    st.markdown("""
    - \( \Delta C \): 혼잡도 개선량(%)  
    - \( C_{\text{base}} - C_{\text{pred}} \): 교통 개선 효과의 절대값  

    👉 교통영향평가 협의 시, 혼잡도 개선율이 일정 수준(예: 5%) 이상이면 교통개선 근거로 활용할 수 있습니다.
    """)

    # 3️⃣ 재무 계산
    st.header("③ 매출 및 비용 계산")
    st.latex(r"""
    R_{\text{won}} = A_{\text{sellable}} \times P_{\text{sale}} \times R_{\text{sale}}
    """)
    st.markdown("""
    - \( R_{\text{won}} \): 총 매출액(만원)  
    - \( P_{\text{sale}} \): 분양가(만원/㎡)  
    - \( R_{\text{sale}} \): 분양률(%)  

    👉 분양 가능한 면적에 분양가와 분양률을 곱해 **총 매출액(만원 단위)** 을 구합니다.
    """)

    st.latex(r"""
    C_{\text{won}} = A_{\text{sellable}} \times P_{\text{build}}
    """)
    st.markdown("""
    - \( C_{\text{won}} \): 총 공사비(만원)  
    - \( P_{\text{build}} \): 공사비 단가(만원/㎡)

    👉 전체 분양면적에 단가를 곱하여 **총 공사비(만원)** 을 계산합니다.
    """)

    st.latex(r"""
    R_{\text{bil}} = \frac{R_{\text{won}}}{10^4 \times 100}, \quad
    C_{\text{bil}} = \frac{C_{\text{won}}}{10^4 \times 100} + I_{\text{infra}}
    """)
    st.markdown("""
    - \( R_{\text{bil}} \): 총 매출(억원)  
    - \( C_{\text{bil}} \): 총 사업비(억원)  
    - \( I_{\text{infra}} \): 교통 등 인프라 투자비(억원)  

    ⚠️ 코드상에서는 `만원 → 억원` 변환을 `/10,000/100 = /1,000,000` 으로 수행하므로, 실제 단위 정합성 확인이 필요합니다.
    """)

    # 4️⃣ 수익성 지표
    st.header("④ 이익, 마진율, NPV, 회수기간")
    st.latex(r"""
    \Pi = R_{\text{bil}} - C_{\text{bil}}
    """)
    st.markdown("""
    - \( \Pi \): 총이익(억원)  
    👉 단순히 총매출에서 총비용을 뺀 값입니다.
    """)

    st.latex(r"""
    M = \frac{\Pi}{C_{\text{bil}}} \times 100
    """)
    st.markdown("""
    - \( M \): 마진율(%)  
    👉 투자 대비 순이익 비율을 의미합니다.
    """)

    st.latex(r"""
    CF_{\text{annual}} = \frac{\Pi}{Y}
    """)
    st.markdown("""
    - \( CF_{\text{annual}} \): 연간 순현금흐름(억원/년)  
    - \( Y \): 회수기간(년)

    👉 전체 이익을 회수기간 동안 균등하게 나눈다고 가정합니다.
    """)

    st.latex(r"""
    NPV = \sum_{t=1}^{Y} \frac{CF_{\text{annual}}}{(1 + r)^t}
    """)
    st.markdown("""
    - \( NPV \): 순현재가치(억원)  
    - \( r \): 할인율(%)  

    👉 미래 현금흐름을 현재가치로 환산한 값으로, **사업의 경제적 타당성**을 평가할 때 사용됩니다.  
    NPV > 0이면 수익성 있는 사업으로 간주됩니다.
    """)

    st.latex(r"""
    \text{Payback} = \left\lceil \frac{C_{\text{bil}}}{CF_{\text{annual}}} \right\rceil
    """)
    st.markdown("""
    👉 초기 투자비를 회수하는 데 걸리는 최소 연수를 정수로 계산한 것입니다.  
    값이 작을수록 빠른 회수, 즉 **자금 회전율이 높음**을 의미합니다.
    """)

    # 5️⃣ 민감도 분석
    st.header("⑤ 민감도 분석 (토네이도 차트)")
    st.markdown("""
    각 변수(분양가·공사비·버스증편·인프라비)의 ±% 변화를 가정하여,  
    그 변화가 NPV에 미치는 영향을 비교합니다.

    \[
    \Delta NPV_i = NPV_i^{(+)} - NPV_i^{(-)}
    \]

    👉 막대가 클수록 **해당 변수에 NPV가 민감하게 반응**한다는 뜻입니다.  
    예를 들어 공사비 변동폭이 가장 크다면, 사업성은 공사비 변화에 매우 취약합니다.
    """)

    # 6️⃣ 확률 분석
    st.header("⑥ 확률 분석 (Monte Carlo Simulation)")
    st.markdown(r"""
    \[
    P_{\text{sale}} \sim \mathcal{N}(\mu_{\text{sale}}, \sigma_{\text{sale}}), \quad
    P_{\text{cost}} \sim \mathcal{N}(\mu_{\text{cost}}, \sigma_{\text{cost}})
    \]

    - 분양가와 공사비를 정규분포로 가정하여 N회 샘플링  
    - 각 조합별로 NPV를 계산 → 분포 분석

    P10, P50, P90:
    - **P10**: 보수적 시나리오(하위 10%)  
    - **P50**: 중앙값(기대값)  
    - **P90**: 낙관적 시나리오(상위 10%)

    👉 이 범위를 통해 **리스크 허용 한계**를 정량적으로 파악할 수 있습니다.
    """)

    # 7️⃣ 종합 해석
    st.header("⑦ 종합 해석 및 활용")
    st.markdown("""
    - `NPV` : **재무적 타당성**  
    - `혼잡도 개선 ΔC` : **사회적·교통효과**  
    - `마진율 M` : **사업 효율성 지표**  
    - `Payback` : **자금 회전 속도**  

    이 네 가지 지표를 종합적으로 해석하면,  
    “사업의 재무성과 + 사회적 편익(교통개선)”을 동시에 고려한 **스마트 인프라 투자 의사결정**이 가능합니다.
    """)

    st.info("💡 모든 수식은 간이모델 기반이므로 실제 적용 시, 교통수요예측·현금흐름 일정 등 세부 모델링이 필요합니다.")

if __name__ == "__main__":
    app()
