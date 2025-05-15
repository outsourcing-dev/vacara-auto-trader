import os
import sys
import re
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlparse, parse_qs

# 상위 디렉토리 모듈 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("url_extractor")

class URLExtractor:
    """WebSocket URL에서 필요한 연결 정보를 추출하는 클래스"""
    
    @staticmethod
    def extract_baccarat_config(ws_url: str) -> Optional[Dict[str, str]]:
        """
        WebSocket URL에서 바카라 설정 정보 추출
        
        Args:
            ws_url: 바카라 WebSocket URL
            
        Returns:
            설정 정보 딕셔너리 또는 실패 시 None
        """
        try:
            # URL 파싱
            parsed_url = urlparse(ws_url)
            query_params = parse_qs(parsed_url.query)
            
            # 경로에서 bare_session_id 추출
            path_parts = parsed_url.path.split('/')
            bare_session_id = path_parts[-1]
            
            # 쿼리 파라미터에서 값 추출
            session_id = query_params.get('EVOSESSIONID', [''])[0]
            
            # instance 파라미터 처리 (하이픈으로 분리된 첫 부분만 사용)
            instance_param = query_params.get('instance', [''])[0]
            instance = instance_param.split('-')[0] if instance_param else ''
            
            client_version = query_params.get('client_version', [''])[0]
            
            # 필수 값 확인
            if not all([bare_session_id, session_id, instance, client_version]):
                logger.warning("URL에서 필수 설정값을 추출할 수 없습니다.")
                return None
            
            return {
                "session_id": session_id,
                "bare_session_id": bare_session_id,
                "instance": instance,
                "client_version": client_version
            }
        except Exception as e:
            logger.error(f"URL 파싱 오류: {e}")
            return None
    
    @staticmethod
    def extract_room_websocket_url(lobby_ws_url: str, room_id: str) -> Optional[str]:
        """
        로비 WebSocket URL을 기반으로 특정 방의 WebSocket URL 생성
        
        Args:
            lobby_ws_url: 로비 WebSocket URL
            room_id: 방 ID
            
        Returns:
            방 WebSocket URL 또는 실패 시 None
        """
        try:
            # 기본 정보 추출
            config = URLExtractor.extract_baccarat_config(lobby_ws_url)
            if not config:
                return None
            
            # 방 URL 패턴 생성
            # 실제 구현에서는 정확한 URL 패턴을 파악해야 함
            # 이 예시는 추측에 기반한 가상의 패턴임
            room_ws_url = (
                f"wss://skylinestart.evo-games.com/public/game/socket/{room_id}/{config['bare_session_id']}"
                f"?messageFormat=json"
                f"&device=Desktop"
                f"&instance={config['instance']}-{config['bare_session_id']}-"
                f"&EVOSESSIONID={config['session_id']}"
                f"&client_version={config['client_version']}"
            )
            
            return room_ws_url
        except Exception as e:
            logger.error(f"방 URL 생성 오류: {e}")
            return None
    
    @staticmethod
    def validate_ws_url(ws_url: str) -> bool:
        """
        WebSocket URL 유효성 검사
        
        Args:
            ws_url: 검사할 WebSocket URL
            
        Returns:
            유효성 여부
        """
        if not ws_url:
            return False
        
        # 기본 형식 및 도메인 검사
        try:
            parsed_url = urlparse(ws_url)
            
            # 프로토콜 확인
            if parsed_url.scheme not in ['ws', 'wss']:
                return False
            
            # 도메인 확인
            if 'evo-games.com' not in parsed_url.netloc:
                return False
            
            # 경로 확인
            if not re.search(r'/socket/v2/|/game/socket/', parsed_url.path):
                return False
            
            # 쿼리 파라미터 확인
            query_params = parse_qs(parsed_url.query)
            required_params = ['EVOSESSIONID', 'instance', 'client_version']
            
            if not all(param in query_params for param in required_params):
                return False
            
            return True
            
        except Exception:
            return False