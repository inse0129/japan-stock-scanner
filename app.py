# app.py
import streamlit as st
import engine  # 방금 만든 백엔드 로직 불러오기
import time

# 1. 페이지 기본 설정
st.set_page_config(page_title="J-Stock Scanner", page_icon="📈", layout="centered")

# 2. 세션 상태(RAM 임시 저장소) 초기화
if "is_verified" not in st.session_state:
    st.session_state.is_verified = False
    st.session_state.plan = ""
    st.session_state.max_cost = 0
    st.session_state.api_key = ""

# --- [UI: 헤더 섹션] ---
st.title("📈 J-Stock Scanner")
st.markdown("**J-Quants API**의 힘을 100% 끌어내는 초고속 조건검색기")
st.divider()

# --- [UI: 인증 전 화면 (The Handshake)] ---
if not st.session_state.is_verified:
    st.subheader("🔑 API 키 연동 (BYOK)")
    st.info("고객님의 J-Quants API Key를 입력해 주세요. (서버에 영구 저장되지 않으며, 브라우저 종료 시 증발합니다.)")
    
    user_api_key = st.text_input("J-Quants API Key", type="password", placeholder="여기에 키를 붙여넣으세요")
    
    if st.button("🚀 API 연동 및 플랜 검증", use_container_width=True):
        if user_api_key:
            with st.spinner("서버와 통신하며 권한(Plan)을 스캔 중입니다... (최대 3초 소요)"):
                # 폭포수 검증 실행!
                result = engine.verify_jquants_plan(user_api_key)
                
                # 결과 세션에 저장
                st.session_state.plan = result["plan"]
                st.session_state.max_cost = result["max_cost"]
                st.session_state.is_verified = True
                st.session_state.api_key = user_api_key
                st.session_state.message = result["message"]
                
                st.rerun() # 화면 새로고침하여 다음 UI 띄우기
        else:
            st.warning("API 키를 먼저 입력해 주세요!")

# --- [UI: 인증 후 화면 (Gamification Dashboard)] ---
else:
    # 1. 성공 메시지 및 등급 안내
    st.success(f"**검증 완료!** 환영합니다. 고객님의 플랜은 **[{st.session_state.plan}]** 입니다.")
    
    # 2. 게임 같은 코스트(Cost) 계기판 UI
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"*{st.session_state.message}*")
        st.progress(0, text=f"🔋 현재 덱 코스트: [ 0 / {st.session_state.max_cost} ]")
    with col2:
        if st.button("🔌 연결 해제"):
            st.session_state.clear()
            st.rerun()
            
    st.divider()
    
    # 3. 조건식 조립 공간 (다음 단계 개발 예정)
    st.subheader("🛠️ 나만의 조건식 조립하기")
    st.caption("아래에서 원하는 조건을 체크하세요. 각 조건마다 Cost가 소모됩니다.")
    
    # (테스트용 가짜 UI)
    st.checkbox(f"당일 양봉 마감 (Cost: 1)")
    st.checkbox(f"전일 대비 거래량 500% 이상 (Cost: 2)")
    
    if st.session_state.plan == "Free":
        st.error("🔒 20일 이동평균선 돌파 (Cost: 20) ➡️ J-Quants Light 이상 결제 필요")
    else:
        st.checkbox(f"20일 이동평균선 돌파 (Cost: 20)")
        
    st.button("🎯 조건 검색 실행!", type="primary", use_container_width=True)
