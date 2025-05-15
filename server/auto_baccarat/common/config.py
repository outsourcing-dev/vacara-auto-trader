import os
import sys
import logging
from typing import Dict, Any

# 상위 디렉토리 모듈 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("config")

class Config:
    """프로그램 기본 설정"""
    
    # 서버 설정
    SERVER_HOST = "0.0.0.0"
    SERVER_PORT = 8080
    
    # 로깅 설정
    LOG_LEVEL = logging.INFO
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # 세션 설정
    SESSION_EXPIRY_DAYS = 7
    
    # 기본 연패 설정
    DEFAULT_PLAYER_STREAK = 3
    DEFAULT_BANKER_STREAK = 3
    DEFAULT_MIN_RESULTS = 10
    
    # 기본 베팅 설정
    DEFAULT_BET_AMOUNT = 1000
    DEFAULT_MAX_ROUNDS = 10
    DEFAULT_BET_STRATEGY = "follow_streak"
    
    # 기본 예측 알고리즘 설정
    DEFAULT_PREDICTION_ALGORITHM = "pattern_recognition"
    DEFAULT_SAMPLE_SIZE = 15
    DEFAULT_CONFIDENCE_THRESHOLD = 0.6
    
    # WebSocket 관련 설정
    WS_PING_INTERVAL = 30  # 초
    WS_PING_TIMEOUT = 10   # 초
    
    # 클라이언트 헤더 설정
    DEFAULT_HEADERS = {
        "Origin": "https://skylinestart.evo-games.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }
    
    @classmethod
    def get_default_streak_settings(cls) -> Dict[str, Any]:
        """기본 연패 설정 반환"""
        return {
            "player_streak": cls.DEFAULT_PLAYER_STREAK,
            "banker_streak": cls.DEFAULT_BANKER_STREAK,
            "min_results": cls.DEFAULT_MIN_RESULTS
        }
    
    @classmethod
    def get_default_betting_settings(cls) -> Dict[str, Any]:
        """기본 베팅 설정 반환"""
        return {
            "amount": cls.DEFAULT_BET_AMOUNT,
            "max_rounds": cls.DEFAULT_MAX_ROUNDS,
            "strategy": cls.DEFAULT_BET_STRATEGY
        }
    
    @classmethod
    def get_default_prediction_settings(cls) -> Dict[str, Any]:
        """기본 예측 알고리즘 설정 반환"""
        return {
            "algorithm": cls.DEFAULT_PREDICTION_ALGORITHM,
            "sample_size": cls.DEFAULT_SAMPLE_SIZE,
            "confidence_threshold": cls.DEFAULT_CONFIDENCE_THRESHOLD
        }