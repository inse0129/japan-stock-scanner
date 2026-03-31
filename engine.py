import pandas as pd
from datetime import datetime, timedelta
import time
import jpholiday
import requests  # 🎯 대표님의 픽! 공식 라이브러리로 복귀!

# ==========================================
# 1. API 플랜 검증 로직 (폭포수 찌르기)
# ==========================================
def verify_jquants_plan(api_key):
    """jquantsapi 클라이언트를 이용해 토큰 갱신과 권한 스캔을 완벽하게 처리합니다."""
    # J-Quants 클라이언트 생성 (ID Token 자동 발급 마법)
    cli = jquantsapi.Client(refresh_token=api_key)
    
    def check_past_date(days_ago):
        target_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y%m%d')
        try:
            # 토요타(72030) 종목만 찔러서 해당 과거 데이터에 접근 가능한지 권한 테스트
            df = cli.get_prices_daily_quotes(code="72030", date_yyyymmdd=target_date)
            return not df.empty
        except:
            return False

    if not check_past_date(180): return {"plan": "Free", "max_cost": 3, "message": "단기/급등 스캐너 무료 제공"}
    time.sleep(0.1)
    if not check_past_date(365 * 6): return {"plan": "Light", "max_cost": 20, "message": "기본 스윙 조건식 개방"}
    time.sleep(0.1)
    if not check_past_date(365 * 11): return {"plan": "Standard", "max_cost": 100, "message": "HTS급 강력한 스윙 조건식 개방"}
    return {"plan": "Premium", "max_cost": 450, "message": "제한 없는 무제한 딥스캔 활성화"}


# ==========================================
# 2. 데이터 수집기 (마스터 트레이딩 캘린더 탑재)
# ==========================================
def get_recent_trading_days(n_days, base_date=None):
    if base_date is None:
        base_date = datetime.now()
        
    # J-Quants 데이터 배포 시간(17시) 고려
    if base_date.date() == datetime.now().date() and datetime.now().hour < 17:
        base_date -= timedelta(days=1)
        
    dates = []
    current_date = base_date
    
    while len(dates) < n_days:
        # 주말(토,일) 제외 AND 일본 공휴일(jpholiday) 완벽 제외
        if current_date.weekday() < 5 and not jpholiday.is_holiday(current_date):
            dates.append(current_date.strftime('%Y%m%d'))
        current_date -= timedelta(days=1)
        
    return dates

def fetch_daily_market(cli, date_str, cache_dict):
    """jquantsapi를 사용해 특정 날짜의 전종목 주가를 수집하고 캐싱합니다."""
    if date_str in cache_dict:
        return cache_dict[date_str]
        
    try:
        # code 파라미터 없이 날짜만 넣으면 전종목 4000개가 한방에 반환됩니다.
        df = cli.get_prices_daily_quotes(date_yyyymmdd=date_str)
        if df is None or df.empty:
            return pd.DataFrame()
            
        # 연산을 위해 숫자로 변환
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
def run_scanner(api_key, plan, cond1_active, cond2_active, cond3_active, cache_dict):
    # API 클라이언트 초기화
    cli = jquantsapi.Client(refresh_token=api_key)
    
    # 플랜별 타임머신 로직 
    if plan == "Free":
        # 무료 유저는 무조건 60 '영업일(공휴일 뺀 순수 장 열린 날)' 전으로 타임루프!
        past_trading_days = get_recent_trading_days(62) 
        today_str = past_trading_days[60]
        yest_str = past_trading_days[61]
        target_date_for_ui = today_str
    else:
        # 유료 유저는 최신 2일치
        trading_days = get_recent_trading_days(2) 
        today_str = trading_days[0]
        yest_str = trading_days[1]
        target_date_for_ui = today_str

    # 데이터 호출
    df_today = fetch_daily_market(cli, today_str, cache_dict)
    df_yest = fetch_daily_market(cli, yest_str, cache_dict)
    
    if df_today.empty or df_yest.empty:
        return pd.DataFrame(), target_date_for_ui
        
    # 지퍼 채우기 (Merge)
    df_merged = pd.merge(df_today, df_yest, on='Code', suffixes=('_today', '_yest'))
    mask = pd.Series(True, index=df_merged.index)
    
    # 조건 1: 양봉 마감
    if cond1_active:
        if 'Close_today' in df_merged.columns and 'Open_today' in df_merged.columns:
            mask = mask & (df_merged['Close_today'] > df_merged['Open_today'])
        
    # 조건 2: 전일 대비 거래대금 500% 이상
    if cond2_active:
        if 'TurnoverValue_today' in df_merged.columns and 'TurnoverValue_yest' in df_merged.columns:
            mask = mask & (df_merged['TurnoverValue_today'] >= (df_merged['TurnoverValue_yest'] * 5))
            
    # 조건 3: 20일 이평선 돌파 (PRO 유저용, 차후 개발)
    if cond3_active:
        pass 
        
    final_result = df_merged[mask]
    
    # 화면 출력용 깔끔한 표 정리
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
