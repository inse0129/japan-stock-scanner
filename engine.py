import requests
import pandas as pd
from datetime import datetime, timedelta
import time

# ==========================================
# 1. API 플랜 검증 로직 (이전 단계 완성본)
# ==========================================
def verify_jquants_plan(api_key):
    # (이전 코드와 동일 - 약한 고리부터 찌르는 폭포수 검증)
    url = "https://api.jquants.com/v2/quotes/daily"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    def check_past_date(days_ago):
        target_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y%m%d')
        params = {"code": "72030", "date": target_date}
        try:
            res = requests.get(url, headers=headers, params=params, timeout=5)
            return res.status_code == 200
        except:
            return False

    if not check_past_date(180): return {"plan": "Free", "max_cost": 3, "message": "단기/급등 스캐너 무료 제공"}
    time.sleep(0.1)
    if not check_past_date(365 * 6): return {"plan": "Light", "max_cost": 20, "message": "기본 스윙 조건식 개방"}
    time.sleep(0.1)
    if not check_past_date(365 * 11): return {"plan": "Standard", "max_cost": 100, "message": "HTS급 강력한 스윙 조건식 개방"}
    return {"plan": "Premium", "max_cost": 450, "message": "제한 없는 무제한 딥스캔 활성화"}


# ==========================================
# 2. 데이터 수집기 (세션 캐시 적용 완료!)
# ==========================================
def get_recent_trading_days(n_days, base_date=None):
    """플랜에 따른 기준일(base_date)부터 과거 영업일 N개를 구합니다."""
    if base_date is None:
        base_date = datetime.now()
        
    dates = []
    current_date = base_date
    
    while len(dates) < n_days:
        if current_date.weekday() < 5: # 주말 제외
            dates.append(current_date.strftime('%Y%m%d'))
        current_date -= timedelta(days=1)
    return dates

def fetch_daily_market(api_key, date_str, cache_dict):
    """특정 날짜의 '전종목' 주가를 한 번에 가져와서 캐시에 저장하거나 꺼내옵니다."""
    
    # 🛡️ 1. 캐시 확인 (사물함에 이미 데이터가 있다면 API 호출 0회!)
    if date_str in cache_dict:
        return cache_dict[date_str]
        
    # 📡 2. 캐시에 없다면 J-Quants API 호출 (API 1회 소모)
    url = "https://api.jquants.com/v2/quotes/daily"
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"date": date_str} # code를 지정하지 않으면 전종목이 옵니다!
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json().get("daily_quotes", [])
        df = pd.DataFrame(data)
        
        # 숫자형 데이터로 변환 (결측치 제거)
        numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume', 'TurnoverValue']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        # 💾 3. 가져온 데이터를 유저의 세션 캐시에 저장 (창 닫으면 폭파됨)
        cache_dict[date_str] = df
        return df
    else:
        # 주말이나 휴일이라 데이터가 없는 경우 빈 데이터프레임 반환
        return pd.DataFrame()


# ==========================================
# 3. 🚀 스캐너 엔진 (지퍼 채우기 및 판다스 벡터 연산)
# ==========================================
# 기존 run_scanner 함수를 아래로 교체 (매개변수에 plan 추가!)
def run_scanner(api_key, plan, cond1_active, cond2_active, cond3_active, cache_dict):
    """플랜을 인식하여 기준일을 자동으로 맞추고 검색을 수행합니다."""
    
    # 🕰️ 핵심: 플랜별 타임머신 로직
    if plan == "Free":
        # 무료 플랜은 J-Quants 정책상 12주(84일) 전이 가장 '최신' 데이터입니다.
        target_base_date = datetime.now() - timedelta(days=84)
    else:
        # 유료 플랜은 오늘을 기준으로 합니다.
        target_base_date = datetime.now()

    # 타겟 기준일로부터 2일치 영업일 추출
    trading_days = get_recent_trading_days(2, base_date=target_base_date) 
    today_str = trading_days[0]
    yest_str = trading_days[1]
    
    df_today = fetch_daily_market(api_key, today_str, cache_dict)
    df_yest = fetch_daily_market(api_key, yest_str, cache_dict)
    
    # 빈 데이터 방어 (휴일 등으로 못 가져왔을 때)
    if df_today.empty or df_yest.empty:
        return pd.DataFrame(), today_str # 기준일 문자열도 함께 반환
        
    # 지퍼 채우기 (Merge)
    df_merged = pd.merge(df_today, df_yest, on='Code', suffixes=('_today', '_yest'))
    
    mask = pd.Series(True, index=df_merged.index)
    
    if cond1_active:
        mask = mask & (df_merged['Close_today'] > df_merged['Open_today'])
        
    if cond2_active:
        mask = mask & (df_merged['TurnoverValue_today'] >= (df_merged['TurnoverValue_yest'] * 5))
        
    final_result = df_merged[mask]
    
    display_df = final_result[['Code', 'Close_today', 'Volume_today', 'TurnoverValue_today']].copy()
    display_df.columns = ['종목코드', '현재가(엔)', '당일 거래량', '거래대금(엔)']
    display_df = display_df.sort_values(by='거래대금(엔)', ascending=False)
    
    # 💡 화면에 띄워줄 '실제 검색된 기준일(today_str)'도 같이 넘겨줍니다!
    return display_df, today_str
