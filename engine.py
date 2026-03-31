import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import jpholiday

# ==========================================
# 1. API 플랜 검증 로직 (J-Quants V2 완벽 호환)
# ==========================================
def verify_jquants_plan(api_key):
    """V2 API: 데이터 존재 여부를 더 엄격하게 체크하여 플랜을 판별합니다."""
    url = "https://api.jquants.com/v2/equities/bars/daily"
    headers = {"x-api-key": api_key}
    
    def is_data_accessible(days_ago):
        # 특정 시점의 토요타(72030) 데이터를 찔러봄
        target_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y%m%d')
        params = {"code": "72030", "date": target_date}
        try:
            res = requests.get(url, headers=headers, params=params, timeout=5)
            if res.status_code == 200:
                data = res.json().get("data", [])
                # 🎯 핵심 수정: 리스트가 비어있지 않고, 실제 주가 정보가 들어있어야 '권한 있음'으로 간주
                return len(data) > 0 and "C" in data[0] 
            return False
        except:
            return False

    # 1단계: 6개월 전 테스트 (무료 유저는 여기서 True가 나와야 함, 유료 유저는 당연히 True)
    # 만약 여기서 False가 나오면 키 자체가 잘못되었거나 시스템 오류입니다.
    if not is_data_accessible(180):
        # 💡 반대로, 오늘(최신) 데이터를 찔러서 안 나오면 무조건 Free입니다.
        if not is_data_accessible(1): 
            return {"plan": "Free", "max_cost": 3, "message": "단기/급등 스캐너 무료 제공 (12주 전 데이터 기준)"}
        return {"plan": "Unknown", "max_cost": 0, "message": "키 검증 실패"}

    # 2단계: 6년 전 테스트 (무료는 2년까지만 주므로 여기서 무조건 False가 나와야 함)
    time.sleep(0.1)
    if not is_data_accessible(365 * 6):
        return {"plan": "Free", "max_cost": 3, "message": "단기/급등 스캐너 무료 제공 (12주 전 데이터 기준)"}
        
    # 3단계: 11년 전 테스트 (Light는 5년까지만 주므로 여기서 False)
    time.sleep(0.1)
    if not is_data_accessible(365 * 11):
        return {"plan": "Light", "max_cost": 20, "message": "기본 스윙 조건식 개방"}
        
    # 4단계: Standard 판별
    time.sleep(0.1)
    if not is_data_accessible(365 * 21):
        return {"plan": "Standard", "max_cost": 100, "message": "HTS급 강력한 스윙 조건식 개방"}
        
    return {"plan": "Premium", "max_cost": 450, "message": "제한 없는 무제한 딥스캔 활성화"}

# ==========================================
# 2. 데이터 수집기 (V2 전용)
# ==========================================
def get_recent_trading_days(n_days, base_date=None):
    if base_date is None:
        base_date = datetime.now()
        
    if base_date.date() == datetime.now().date() and datetime.now().hour < 17:
        base_date -= timedelta(days=1)
        
    dates = []
    current_date = base_date
    
    while len(dates) < n_days:
        if current_date.weekday() < 5 and not jpholiday.is_holiday(current_date):
            dates.append(current_date.strftime('%Y%m%d'))
        current_date -= timedelta(days=1)
        
    return dates

def fetch_daily_market(api_key, date_str, cache_dict):
    """V2 API를 사용하여 특정 날짜의 전종목 주가를 수집합니다."""
    if date_str in cache_dict:
        return cache_dict[date_str]
        
    url = "https://api.jquants.com/v2/equities/bars/daily"
    headers = {"x-api-key": api_key}
    params = {"date": date_str}
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json().get("data", [])
        if not data:
            return pd.DataFrame()
            
        df = pd.DataFrame(data)
        
        # 🎯 V2 API 컬럼명 반영: O(始値), H(高値), L(安値), C(終値), Vo(出来高), Va(売買代金)
        numeric_cols = ['O', 'H', 'L', 'C', 'Vo', 'Va']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        cache_dict[date_str] = df
        return df
    else:
        return pd.DataFrame()


# ==========================================
# 3. 🚀 스캐너 엔진 (V2 데이터 기반)
# ==========================================
def run_scanner(api_key, plan, cond1_active, cond2_active, cond3_active, cache_dict):
    if plan == "Free":
        past_trading_days = get_recent_trading_days(62) 
        today_str = past_trading_days[60]
        yest_str = past_trading_days[61]
        target_date_for_ui = today_str
    else:
        trading_days = get_recent_trading_days(2) 
        today_str = trading_days[0]
        yest_str = trading_days[1]
        target_date_for_ui = today_str

    df_today = fetch_daily_market(api_key, today_str, cache_dict)
    df_yest = fetch_daily_market(api_key, yest_str, cache_dict)
    
    if df_today.empty or df_yest.empty:
        return pd.DataFrame(), target_date_for_ui
        
    df_merged = pd.merge(df_today, df_yest, on='Code', suffixes=('_today', '_yest'))
    mask = pd.Series(True, index=df_merged.index)
    
    # 🎯 조건 1: 당일 양봉 (V2 컬럼 C_today > O_today)
    if cond1_active:
        if 'C_today' in df_merged.columns and 'O_today' in df_merged.columns:
            mask = mask & (df_merged['C_today'] > df_merged['O_today'])
        
    # 🎯 조건 2: 전일 대비 거래대금 500% 폭발 (V2 컬럼 Va_today >= Va_yest * 5)
    if cond2_active:
        if 'Va_today' in df_merged.columns and 'Va_yest' in df_merged.columns:
            mask = mask & (df_merged['Va_today'] >= (df_merged['Va_yest'] * 5))
            
    if cond3_active:
        pass 
        
    final_result = df_merged[mask]
    
    # 🎯 화면 출력용 테이블 정리 (V2 컬럼 기준)
    cols_to_show = ['Code', 'C_today', 'Vo_today', 'Va_today']
    display_df = final_result[[c for c in cols_to_show if c in final_result.columns]].copy()
    
    display_df.rename(columns={
        'Code': '종목코드', 
        'C_today': '현재가(엔)', 
        'Vo_today': '당일 거래량', 
        'Va_today': '거래대금(엔)'
    }, inplace=True)
    
    if '거래대금(엔)' in display_df.columns:
        display_df = display_df.sort_values(by='거래대금(엔)', ascending=False)
    
    return display_df, target_date_for_ui
