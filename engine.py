import pandas as pd
from datetime import datetime, timedelta
import time
import jpholiday
import requests

# ==========================================
# 0. API 토큰 발급 헬퍼 (New!)
# ==========================================
def get_id_token(refresh_token):
    """리프레시 토큰을 사용해 J-Quants API의 임시 통행증(ID Token)을 직접 발급받습니다."""
    url = f"https://api.jquants.com/v1/token/auth_refresh?refreshtoken={refresh_token}"
    res = requests.post(url)
    if res.status_code == 200:
        return res.json().get("idToken")
    return None

# ==========================================
# 1. API 플랜 검증 로직 (폭포수 찌르기 - requests 버전)
# ==========================================
def verify_jquants_plan(refresh_token):
    # 1단계: API 키(리프레시 토큰) 유효성 검증
    id_token = get_id_token(refresh_token)
    
    if not id_token:
        return {"plan": "Invalid", "max_cost": 0, "message": "API 키(Refresh Token)가 만료되었습니다. J-Quants 홈페이지에서 새로 발급(Get Refresh Token) 받아주세요!"}

    headers = {"Authorization": f"Bearer {id_token}"}

    def check_past_date(days_ago):
        target_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y%m%d')
        # 토요타(72030) 종목만 찔러서 과거 데이터 권한 테스트
        url = f"https://api.jquants.com/v1/prices/daily_quotes?code=72030&date={target_date}"
        try:
            r = requests.get(url, headers=headers)
            if r.status_code == 200:
                data = r.json()
                # 데이터가 존재하면 권한이 있는 것
                if "daily_quotes" in data and len(data["daily_quotes"]) > 0:
                    return True
            return False
        except:
            return False

    # 2단계: 과거 데이터 권한으로 플랜을 역추적합니다.
    if check_past_date(365 * 11): 
        return {"plan": "Standard", "max_cost": 100, "message": "HTS급 강력한 스윙 조건식 개방"}
    time.sleep(0.1)
    
    if check_past_date(365 * 6): 
        return {"plan": "Light", "max_cost": 20, "message": "기본 스윙 조건식 개방"}
    
    # 키는 유효하지만 과거 데이터 접근이 제한적이라면 Free 플랜입니다.
    return {"plan": "Free", "max_cost": 3, "message": "단기/급등 스캐너 무료 제공"}

# ==========================================
# 2. 데이터 수집기 (마스터 트레이딩 캘린더 탑재)
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

def fetch_daily_market(id_token, date_str, cache_dict):
    """requests를 사용해 특정 날짜의 전종목 주가를 수집하고 캐싱합니다."""
    if date_str in cache_dict:
        return cache_dict[date_str]
        
    headers = {"Authorization": f"Bearer {id_token}"}
    url = f"https://api.jquants.com/v1/prices/daily_quotes?date={date_str}"
    
    try:
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            return pd.DataFrame()
            
        data = r.json()
        if "daily_quotes" not in data or not data["daily_quotes"]:
            return pd.DataFrame()
            
        df = pd.DataFrame(data["daily_quotes"])
            
        numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume', 'TurnoverValue']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        cache_dict[date_str] = df
        return df
    except Exception as e:
        return pd.DataFrame()

# ==========================================
# 3. 🚀 스캐너 엔진 (타임머신 및 지퍼 채우기 로직)
# ==========================================
def run_scanner(refresh_token, plan, cond1_active, cond2_active, cond3_active, cache_dict):
    # 스캔 시작 전 쌩쌩한 통행증(ID Token) 발급
    id_token = get_id_token(refresh_token)
    if not id_token:
        return pd.DataFrame(), "토큰 발급 실패"
        
    # 플랜별 타임머신 로직 
    if plan == "Free":
        safe_free_date = datetime.now() - timedelta(days=90)
        past_trading_days = get_recent_trading_days(2, base_date=safe_free_date) 
        today_str = past_trading_days[0]
        yest_str = past_trading_days[1]
        target_date_for_ui = today_str
    else:
        trading_days = get_recent_trading_days(2) 
        today_str = trading_days[0]
        yest_str = trading_days[1]
        target_date_for_ui = today_str

    # 데이터 호출
    df_today = fetch_daily_market(id_token, today_str, cache_dict)
    df_yest = fetch_daily_market(id_token, yest_str, cache_dict)
    
    if df_today.empty or df_yest.empty:
        return pd.DataFrame(), target_date_for_ui
        
    # 지퍼 채우기 (Merge)
    df_merged = pd.merge(df_today, df_yest, on='Code', suffixes=('_today', '_yest'))
    mask = pd.Series(True, index=df_merged.index)
    
    if cond1_active:
        if 'Close_today' in df_merged.columns and 'Open_today' in df_merged.columns:
            mask = mask & (df_merged['Close_today'] > df_merged['Open_today'])
        
    if cond2_active:
        if 'TurnoverValue_today' in df_merged.columns and 'TurnoverValue_yest' in df_merged.columns:
            mask = mask & (df_merged['TurnoverValue_today'] >= (df_merged['TurnoverValue_yest'] * 5))
            
    if cond3_active:
        pass 
        
    final_result = df_merged[mask]
    
    cols_to_show = ['Code', 'Close_today', 'Volume_today', 'TurnoverValue_today']
    display_df = final_result[[c for c in cols_to_show if c in final_result.columns]].copy()
    
    display_df.rename(columns={
        'Code': '종목코드', 
        'Close_today': '현재가(엔)', 
        'Volume_today': '당일 거래량', 
        'TurnoverValue_today': '거래대금(엔)'
    }, inplace=True)
    
    if '거래대금(엔)' in display_df.columns:
        display_df = display_df.sort_values(by='거래대금(엔)', ascending=False)
    
    return display_df, target_date_for_ui
