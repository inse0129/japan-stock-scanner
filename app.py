import streamlit as st
import pandas as pd
from engine import run_search

st.set_page_config(page_title="일본 증권주 조건검색", layout="centered")

st.title("📈 일본 증권주 조건검색 (MVP)")
st.markdown("""
**J-Quants API**를 활용하여 일본 증권사 종목 중 설정한 조건에 맞는 종목을 찾아냅니다.
💡 **스윙 / 중장기 투자자를 위한 패턴 검색기입니다.** *(무료 API 정책상 최근 12주 이전의 데이터를 기반으로 과거의 유의미한 패턴을 탐색합니다.)*
""")

st.divider()

st.subheader("⚙️ 검색 조건 설정")

api_key = st.text_input("J-Quants API Refresh Token (필수)", type="password", placeholder="발급받은 Refresh Token을 입력하세요")

col1, col2 = st.columns(2)

with col1:
    n_days = st.number_input("조사 기간 (N봉 이내)", min_value=1, max_value=200, value=60, step=1)
    high_pct = st.number_input("전일대비 고가상승률 (%) 이상", min_value=0.0, max_value=1000.0, value=10.0, step=1.0)

with col2:
    condition_type = st.radio("조건 결합 방식", options=['AND', 'OR'], index=0, help="AND: 두 조건 모두 만족 / OR: 둘 중 하나라도 만족")
    vol_ratio = st.number_input("전일대비 거래량비율 (%) 이상", min_value=0.0, max_value=10000.0, value=300.0, step=10.0)

if st.button("🚀 검색 실행", type="primary", use_container_width=True):
    if not api_key:
        st.warning("⚠️ J-Quants API Refresh Token을 먼저 입력해주세요.")
    else:
        with st.spinner("서버에서 대규모 데이터를 일괄 수집하여 분석하고 있습니다. 잠시만 기다려주세요..."):
            result_df = run_search(
                api_key=api_key, 
                n_days=n_days, 
                high_pct=high_pct, 
                vol_ratio=vol_ratio, 
                condition_type=condition_type
            )
            
            st.divider()
            st.subheader("📊 검색 결과")
            
            if result_df is None:
                pass
            elif result_df.empty:
                st.info("조건에 맞는 종목이 없습니다. 조건을 완화하여 다시 검색해보세요.")
            else:
                st.success(f"총 {len(result_df)}개의 종목이 검색되었습니다!")
                st.dataframe(
                    result_df,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "상승률(%)": st.column_config.NumberColumn(format="%.1f%%"),
                        "거래량비율(%)": st.column_config.NumberColumn(format="%.1f%%")
                    }
                )