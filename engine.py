import jquantsapi
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

def run_search(api_key, n_days, high_pct, vol_ratio, condition_type):
    """
    J-Quants API를 이용해 날짜 범위로 전종목 데이터를 일괄 조회한 뒤,
    로컬에서 증권주를 필터링하여 조건을 분석합니다. (API 호출 최소화)
    """
    try:
        cli = jquantsapi.Client(refresh_token=api_key)
        
        # 1. 상장 종목 목록 가져오기 및 증권주(7200) 정보 매핑
        st.toast("🔍 상장 종목 정보를 불러오는 중입니다...")
        df_list = cli.get_listed_info()
        securities_df = df_list[df_list['Sector33Code'] == '7200']
        securities_codes = securities_df['Code'].tolist()
        
        # 종목코드: 종목명 딕셔너리 생성 (나중에 결과 출력용)
        securities_names = dict(zip(securities_df['Code'], securities_df['CompanyName']))
        
        # 2. 조회할 날짜 범위 계산
        # 무료 티어 지연(약 12주=84일)을 안전하게 피하기 위해 90일 전을 기준일(end_date)로 잡습니다.
        # 기준일로부터 n_days 만큼의 영업일이 필요하므로, 주말/공휴일을 고려해 넉넉히 기간을 설정합니다.
        end_date = datetime.now() - timedelta(days=90)
        start_date = end_date - timedelta(days=(n_days * 2) + 30)
        
        start_str = start_date.strftime('%Y%m%d')
        end_str = end_date.strftime('%Y%m%d')
        
        # 3. 전종목 주가 데이터 일괄 호출 (이 부분이 핵심 해결책입니다!)
        st.toast("📥 주가 데이터를 일괄 다운로드 중입니다. (약 10~30초 소요)")
        # code 지정 없이 from/to 만 넘겨서 해당 기간의 모든 종목 데이터를 한 번에 가져옵니다.
        df_all_prices = cli.get_prices_daily_quotes(from_yyyymmdd=start_str, to_yyyymmdd=end_str)
        
        if df_all_prices.empty:
            st.error("데이터를 불러오지 못했습니다. 날짜 범위를 확인해주세요.")
            return None
            
        # 4. 로컬 메모리에서 증권주만 필터링
        df_sec_prices = df_all_prices[df_all_prices['Code'].isin(securities_codes)].copy()
        
        # 5. 종목별로 그룹화하여 조건 검사
        results = []
        grouped = df_sec_prices.groupby('Code')
        
        progress_text = "조건에 맞는 종목을 분석 중입니다..."
        my_bar = st.progress(0, text=progress_text)
        total_codes = len(grouped)
        
        for idx, (code, df_group) in enumerate(grouped):
            # 프로그레스 바 업데이트
            my_bar.progress((idx + 1) / total_codes, text=f"{progress_text} ({idx + 1}/{total_codes})")
            
            # 날짜 오름차순 정렬
            df_group = df_group.sort_values('Date').reset_index(drop=True)
            
            # 데이터가 N봉을 계산하기에 충분한지 확인
            if len(df_group) < (n_days + 1):
                continue
                
            # 최신 N일 + 전일 데이터 추출
            df_recent = df_group.tail(n_days + 1).copy()
            
            df_recent['Prev_Close'] = df_recent['AdjustmentClose'].shift(1)
            df_recent['Prev_Volume'] = df_recent['AdjustmentVolume'].shift(1)
            
            df_eval = df_recent.dropna(subset=['Prev_Close', 'Prev_Volume']).copy()
            df_eval = df_eval.sort_values('Date', ascending=False).reset_index(drop=True)
            
            for bong_idx, daily in df_eval.iterrows():
                bong = bong_idx + 1 # 1봉전, 2봉전...
                
                if daily['Prev_Close'] == 0 or daily['Prev_Volume'] == 0:
                    continue
                    
                high_increase_pct = ((daily['AdjustmentHigh'] - daily['Prev_Close']) / daily['Prev_Close']) * 100
                vol_increase_ratio = (daily['AdjustmentVolume'] / daily['Prev_Volume']) * 100
                
                cond_high = high_increase_pct >= high_pct
                cond_vol = vol_increase_ratio >= vol_ratio
                
                if condition_type == 'AND':
                    is_match = cond_high and cond_vol
                else:
                    is_match = cond_high or cond_vol
                    
                if is_match:
                    # 날짜 포맷팅 안전 처리
                    date_val = daily['Date']
                    if hasattr(date_val, 'strftime'):
                        date_str = date_val.strftime('%Y-%m-%d')
                    else:
                        date_str = str(date_val)[:10]
                        
                    results.append({
                        '종목코드': code,
                        '종목명': securities_names.get(code, '알수없음'),
                        '해당봉': f"{bong}봉전",
                        '상승률(%)': round(high_increase_pct, 1),
                        '거래량비율(%)': round(vol_increase_ratio, 1),
                        '발생일자': date_str
                    })
                    break # 해당 종목에서 조건을 만족하는 가장 최근 봉 1개만 찾고 종료
                    
        my_bar.empty()
        return pd.DataFrame(results)

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
        return None