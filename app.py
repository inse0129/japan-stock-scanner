import streamlit as st
import time
import pandas as pd
import engine  # 우리가 방금 완성한 V2 완벽 대응 백엔드 엔진

# ==========================================
# 1. 페이지 기본 설정 및 보안 캐시 초기화
# ==========================================
st.set_page_config(page_title="J-Stock Scanner (V2)", page_icon="📈", layout="centered")

# [핵심 보안] 세션 상태(RAM) 초기화 - 브라우저 종료 시 모든 정보 증발
if "is_verified" not in st.session_state:
    st.session_state.is_verified = False
    st.session_state.plan = ""
    st.session_state.max_cost = 0
    st.session_state.api_key = ""
    st.session_state.message = ""

# [핵심 최적화] API 호출 절약을 위한 유저 전용 휘발성 사물함
if "ohlcv_cache" not in st.session_state:
    st.session_state["ohlcv_cache"] = {}

# ==========================================
# 2. 메인 헤더
# ==========================================
st.title("📈 J-Stock Scanner (V2)")
st.markdown("**J-Quants V2 API**의 물리적 한계를 뛰어넘는 초고속 조건검색기")
st.divider()

# ==========================================
# 3. API 연동 화면 (인증 전)
# ==========================================
if not st.session_state.is_verified:
    st.subheader("🔑 API 키 연동 (BYOK)")
    st.info("J-Quants 대시보드에서 발급받은 **[V2 전용 API Key]**를 입력해 주세요. \n\n*데이터는 서버에 영구 저장되지 않으며, 브라우저 창을 닫는 즉시 완벽하게 파기됩니다.*")
    
    user_api_key = st.text_input("J-Quants API Key", type="password", placeholder="여기에 키를 붙여넣으세요")
    
    if st.button("🚀 API 연동 및 플랜 스캔", use_container_width=True):
        if user_api_key:
            with st.spinner("J-Quants 서버를 찔러보며 플랜(Plan) 권한을 스캔 중입니다..."):
                # engine.py의 폭포수 검증 로직 실행
                result = engine.verify_jquants_plan(user_api_key)
                
                # 검증 결과를 세션에 저장
                st.session_state.plan = result["plan"]
                st.session_state.max_cost = result["max_cost"]
                st.session_state.message = result["message"]
                st.session_state.api_key = user_api_key
                st.session_state.is_verified = True
                
                st.rerun() # 화면 새로고침하여 대시보드 진입
        else:
            st.warning("API 키를 먼저 입력해 주세요!")

# ==========================================
# 4. 메인 대시보드 및 조건 검색 UI (인증 후)
# ==========================================
else:
    # --- [상단: 유저 상태창] ---
    col1, col2 = st.columns([4, 1])
    with col1:
        st.success(f"**검증 완료!** 환영합니다. 고객님의 플랜은 **[{st.session_state.plan}]** 입니다.")
    with col2:
        if st.button("🔌 연결 해제"):
            st.session_state.clear() # 로그아웃 시 세션 캐시까지 완벽 폭파
            st.rerun()
            
    st.caption(f"💡 {st.session_state.message}")
    
    # --- [중단: 조건식 조립 및 코스트 계산] ---
    st.subheader("🛠️ 나만의 조건식 조립하기")
    
    current_cost = 0 # 실시간 코스트 합산 변수
    
    # 조건 박스 UI 배치
    st.markdown("#### 🟢 일반 등급 조건 (Cost 낮음)")
    cond1 = st.checkbox("당일 양봉 마감 (Cost: 1)")
    if cond1: current_cost += 1
        
    cond2 = st.checkbox("전일 대비 거래대금 500% 이상 폭발 (Cost: 2)")
    if cond2: current_cost += 2
        
    st.markdown("#### 👑 에픽 등급 조건 (Cost 높음, HTS급 스윙)")
    
    # 플랜별 UI 차별화 (업셀링 가드레일)
    cond3 = False
    if st.session_state.plan == "Free":
        st.error("🔒 20일 이동평균선 돌파 (Cost: 20) ➡️ J-Quants Light 플랜 이상 결제 필요")
    else:
        cond3 = st.checkbox("20일 이동평균선 돌파 (Cost: 20)")
        if cond3: current_cost += 20
            
    # --- [코스트 게이지 바] ---
    st.divider()
    st.markdown("### 🔋 덱 코스트 (Mana)")
    
    is_over_cost = current_cost > st.session_state.max_cost
    
    if is_over_cost:
        st.error(f"⚠️ 코스트 한도 초과! [ {current_cost} / {st.session_state.max_cost} ] 조건을 줄이거나 플랜을 업그레이드하세요.")
        st.progress(1.0) 
    else:
        ratio = current_cost / st.session_state.max_cost if st.session_state.max_cost > 0 else 0
        st.info(f"✅ 현재 덱 코스트: [ {current_cost} / {st.session_state.max_cost} ]")
        st.progress(ratio)

    # --- [하단: 검색 실행 버튼] ---
    btn_disabled = is_over_cost or current_cost == 0
    
    if st.button("🎯 조건 검색 실행!", type="primary", use_container_width=True, disabled=btn_disabled):
        with st.spinner("J-Quants에서 데이터를 가져와 판다스(Pandas)로 지퍼를 채우는 중입니다..."):
            
            # 🔥 V2 엔진 본격 가동! (플랜 정보를 넘겨주어 타임머신을 태움)
            result_df, target_date = engine.run_scanner(
                st.session_state.api_key, 
                st.session_state.plan, 
                cond1, cond2, cond3, 
                st.session_state["ohlcv_cache"]
            )
            
            # 검색 완료 메시지 및 UX 최적화 알림 (Free 플랜 타임머신 안내)
            if st.session_state.plan == "Free":
                st.info(f"💡 **Free 플랜 안내:** J-Quants 정책에 따라 가장 최신으로 열람 가능한 과거 영업일(**{target_date[:4]}년 {target_date[4:6]}월 {target_date[6:]}일**)을 기준으로 스캔했습니다. 최신 실시간 스캔을 원하시면 PRO로 업그레이드하세요!")
            else:
                st.success(f"분석 완료! (기준일: {target_date[:4]}-{target_date[4:6]}-{target_date[6:]})")
                
            st.markdown(f"**총 {len(result_df)}개의 종목이 검색되었습니다.**")
            
            # 데이터 표 출력
            st.dataframe(result_df, use_container_width=True, hide_index=True)
