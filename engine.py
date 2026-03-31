# engine.py
import requests
from datetime import datetime, timedelta
import time

def verify_jquants_plan(api_key):
    """
    유저의 API 키를 받아 J-Quants 과거 데이터를 찔러보고 플랜과 최대 코스트를 반환합니다.
    """
    # J-Quants V2 API 엔드포인트 (가정)
    url = "https://api.jquants.com/v2/quotes/daily"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    # [내부 헬퍼 함수] 특정 일수(days_ago) 전의 주가를 찔러보는 함수
    def check_past_date(days_ago):
        target_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y%m%d')
        # 토요타 자동차(72030)를 대표 종목으로 찔러봅니다.
        params = {"code": "72030", "date": target_date}
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=5)
            # 200 OK면 데이터 접근 권한 있음(성공), 그 외(403 등)면 권한 없음(실패)
            return response.status_code == 200
        except:
            return False

    # 🌊 폭포수 검증 시작 (Cascading Probe)
    
    # 1단계: 6개월(약 180일) 전 찌르기
    # Free 플랜은 최근 12주(약 84일)까지만 제공하므로 여기서 무조건 에러가 납니다.
    if not check_past_date(180):
        return {"plan": "Free", "max_cost": 3, "message": "단기/급등 스캐너 무료 제공"}
        
    # 2단계: 6년(약 2190일) 전 찌르기
    # Light 플랜은 5년까지만 제공하므로 여기서 에러가 납니다.
    time.sleep(0.1) # 서버 보호를 위한 0.1초 매너 딜레이
    if not check_past_date(365 * 6):
        return {"plan": "Light", "max_cost": 20, "message": "기본 스윙 조건식 개방"}
        
    # 3단계: 11년(약 4015일) 전 찌르기
    # Standard 플랜은 10년까지만 제공하므로 여기서 에러가 납니다.
    time.sleep(0.1)
    if not check_past_date(365 * 11):
        return {"plan": "Standard", "max_cost": 100, "message": "HTS급 강력한 스윙 조건식 개방"}
        
    # 4단계: 위 3관문을 다 통과했다면 20년 치를 볼 수 있는 가장 비싼 Premium 플랜입니다!
    return {"plan": "Premium", "max_cost": 450, "message": "제한 없는 무제한 딥스캔 활성화"}
