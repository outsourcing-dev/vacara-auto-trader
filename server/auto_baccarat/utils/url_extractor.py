import os
import sys
import re
import logging
from typing import Dict, Any, Optional, Tuple
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
            
            # 도메인 추출
            domain = parsed_url.netloc
            
            # 경로에서 bare_session_id 추출
            path_parts = parsed_url.path.split('/')
            bare_session_id = path_parts[-1]
            
            # 쿼리 파라미터에서 값 추출
            session_id = query_params.get('EVOSESSIONID', [''])[0]
            
            # instance 파라미터 처리 (하이픈으로 분리된 첫 부분만 사용)
            instance_param = query_params.get('instance', [''])[0]
            instance = instance_param.split('-')[0] if instance_param else ''
            
            client_version = query_params.get('client_version', [''])[0]
            
            # 프로토콜 추출 (ws 또는 wss)
            protocol = parsed_url.scheme
            
            # 필수 값 확인
            if not all([bare_session_id, session_id, instance, client_version, domain]):
                logger.warning("URL에서 필수 설정값을 추출할 수 없습니다.")
                return None
            
            return {
                "session_id": session_id,
                "bare_session_id": bare_session_id,
                "instance": instance,
                "client_version": client_version,
                "domain": domain,
                "protocol": protocol
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
            
            # 도메인 및 프로토콜 사용
            domain = config.get('domain', 'skylinestart.evo-games.com')
            protocol = config.get('protocol', 'wss')
            
            # 방 URL 패턴 생성
            room_ws_url = (
                f"{protocol}://{domain}/public/game/socket/{room_id}/{config['bare_session_id']}"
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
            
            # evo-games.com 관련 도메인인지 확인 (여러 서브도메인 허용)
            # 또는 다른 허용 도메인이 있을 경우 추가
            allowed_domains = ['evo-games.com', 'evolution.com', 'evolutiongaming.com', 'babylonvg.evo-games.com']
            if not any(domain in parsed_url.netloc for domain in allowed_domains):
                logger.warning(f"허용되지 않은 도메인: {parsed_url.netloc}")
                return False
            
            # 경로 확인 - 다양한 경로 패턴 허용
            if not re.search(r'/socket/|/game/', parsed_url.path):
                return False
            
            # 쿼리 파라미터 확인
            query_params = parse_qs(parsed_url.query)
            required_params = ['EVOSESSIONID', 'instance', 'client_version']
            
            if not all(param in query_params for param in required_params):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"URL 검증 오류: {e}")
            return False
        
    @staticmethod
    def extract_domain_info(ws_url: str) -> Tuple[str, str]:
        """
        WebSocket URL에서 도메인과 프로토콜 추출
        
        Args:
            ws_url: WebSocket URL
            
        Returns:
            (도메인, 프로토콜) 튜플
        """
        try:
            parsed_url = urlparse(ws_url)
            return parsed_url.netloc, parsed_url.scheme
        except Exception as e:
            logger.error(f"도메인 추출 오류: {e}")
            # 기본값 반환
            return "skylinestart.evo-games.com", "wss"