import jquantsapi
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

# 💡 1단계 방어 및 그물망: 데이터를 한 번만 가져오고, 1시간 동안 메모리에 기억(캐시)합니다.
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_all_data(api_key):
    cli = jquantsapi.Client(refresh_token=api_key)
    
    # 상장 종목 및 증권주(7200) 정보 매핑
    df_list = cli.get_listed_info()
    securities_df = df_list[df_list['Sector33Code'] == '7200']
    securities_codes = securities_df['Code'].tolist()
    securities_names = dict(zip(securities_df['Code'], securities_df['CompanyName']))
    
    # 넓은 그물망: 무조건 오늘부터 과거 150일치(넉넉하게)를 한 번에 요청
    # 무료 유저는 J-Quants가 알아서 12주 전 데이터부터 잘라서 줍니다.
    end_date = datetime.now()
    start_date = end_date - timedelta(days=150)
    
    df_all_prices = cli.get_prices_daily_quotes(
        from_yyyymmdd=start_date.strftime('%Y%m%d'), 
        to_yyyymmdd=end_date.strftime('%Y%m%d')
    )
    
    # 서버 메모리 과부하를 막기 위해 전체 데이터 중 '증권주'만 남기고 버립니다.
    df_sec_prices = df_all_prices[df_all_prices['Code'].isin(securities_codes)].copy()
    
    return df_sec_prices, securities_names

def run_search(api_key, n_days, high_pct, vol_ratio, condition_type):
    """
    저장된 캐시 데이터를 불러와 조건 연산만 초고속으로 수행합니다.
    """
    try:
        # 캐시된 함수 호출 (최초 1회만 시간 소요, 이후 즉시 통과)
        df_sec_prices, securities_names = fetch_all_data(api_key)
        
        if df_sec_prices.empty:
            return pd.DataFrame()
            
        results = []
        grouped = df_sec_prices.groupby('Code')
        
        progress_text = "조건에 맞는 종목을 빠르게 분석 중입니다..."
        my_bar = st.progress(0, text=progress_text)
        total_codes = len(grouped)
        
        for idx, (code, df_group) in enumerate(grouped):
            my_bar.progress((idx + 1) / total_codes, text=f"{progress_text} ({idx + 1}/{total_codes})")
            
            df_group = df_group.sort_values('Date').reset_index(drop=True)
            
            if len(df_group) < (n_days + 1):
                continue
                
            df_recent = df_group.tail(n_days + 1).copy()
            
            df_recent['Prev_Close'] = df_recent['AdjustmentClose'].shift(1)
            df_recent['Prev_Volume'] = df_recent['AdjustmentVolume'].shift(1)
            
            df_eval = df_recent.dropna(subset=['Prev_Close', 'Prev_Volume']).copy()
            df_eval = df_eval.sort_values('Date', ascending=False).reset_index(drop=True)
            
            for bong_idx, daily in df_eval.iterrows():
                bong = bong_idx + 1 
                
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
                    date_val = daily['Date']
                    date_str = date_val.strftime('%Y-%m-%d') if hasattr(date_val, 'strftime') else str(date_val)[:10]
                        
                    results.append({
                        '종목코드': code,
                        '종목명': securities_names.get(code, '알수없음'),
                        '해당봉': f"{bong}봉전",
                        '상승률(%)': round(high_increase_pct, 1),
                        '거래량비율(%)': round(vol_increase_ratio, 1),
                        '발생일자': date_str
                    })
                    break 
                    
        my_bar.empty()
        return pd.DataFrame(results)

    except Exception as e:
        # 에러 발생 시 캐시를 지워서 꼬임 현상 방지
        fetch_all_data.clear()
        st.error(f"데이터를 가져오는 중 오류가 발생했습니다. API 키를 확인해주세요. (상세: {e})")
        return None
