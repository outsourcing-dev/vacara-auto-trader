import os
import sys
import json
import logging
import asyncio
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timedelta

# 상위 디렉토리 모듈 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# WebSocket 모듈 임포트
import websockets
from fastapi import WebSocket

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("lobby_monitor")

class ClientConfig:
    """바카라 클라이언트 연결 설정"""
    def __init__(self, session_id: str, bare_session_id: str, instance: str, client_version: str, domain: str = None, protocol: str = None):
        self.session_id = session_id
        self.bare_session_id = bare_session_id
        self.instance = instance
        self.client_version = client_version
        self.domain = domain or "skylinestart.evo-games.com"  # 기본 도메인
        self.protocol = protocol or "wss"  # 기본 프로토콜
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "session_id": self.session_id,
            "bare_session_id": self.bare_session_id,
            "instance": self.instance,
            "client_version": self.client_version,
            "domain": self.domain,
            "protocol": self.protocol
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'ClientConfig':
        return cls(
            session_id=data["session_id"],
            bare_session_id=data["bare_session_id"],
            instance=data["instance"],
            client_version=data["client_version"],
            domain=data.get("domain", "skylinestart.evo-games.com"),
            protocol=data.get("protocol", "wss")
        )

class BaccaratWebSocketClient:
    """바카라 WebSocket 클라이언트 클래스"""
    
    def __init__(self, config: ClientConfig, 
                 room_mappings: Dict[str, str] = None, 
                 filter_keywords: List[str] = None,
                 on_message_callback: callable = None):
        """
        바카라 WebSocket 클라이언트 초기화
        
        Args:
            config: 클라이언트 설정
            room_mappings: 방 ID와 디스플레이 이름 매핑
            filter_keywords: 필터링할 키워드 목록
            on_message_callback: 메시지 수신 시 호출할 콜백 함수
        """
        self.config = config
        self.websocket = None
        self.is_connected = False
        self.task = None
        self.received_tables: Dict[str, Any] = {}
        self.last_reconnect_attempt = datetime.now()
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3
        
        # 방 이름 매핑 및 필터링 설정
        self.room_mappings = room_mappings or {}
        self.filter_keywords = filter_keywords or []
        
        # 콜백 함수
        self.on_message_callback = on_message_callback
        
    def _build_websocket_url(self) -> str:
        """WebSocket URL 생성"""
        domain = self.config.domain
        protocol = self.config.protocol
        
        return (
            f"{protocol}://{domain}/public/lobby/socket/v2/{self.config.bare_session_id}"
            f"?messageFormat=json"
            f"&device=Desktop"
            f"&features=opensAt%2CmultipleHero%2CshortThumbnails%2CskipInfosPublished%2Csmc%2CuniRouletteHistory%2CbacHistoryV2%2Cfilters%2CtableDecorations"
            f"&instance={self.config.instance}-{self.config.bare_session_id}-"
            f"&EVOSESSIONID={self.config.session_id}"
            f"&client_version={self.config.client_version}"
        )
        
    async def connect(self) -> bool:
        """WebSocket 서버에 연결"""
        if self.is_connected:
            logger.warning("Already connected")
            return True
        
        url = self._build_websocket_url()
        logger.info(f"WebSocket 서버에 연결 중...")
        
        
        # 브라우저와 동일한 인증 헤더 설정
        headers = {
            "Origin": f"https://{self.config.domain}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Cookie": f"EVOSESSIONID={self.config.session_id}"
        }
        
        # 추가 헤더 - Accept 헤더 추가
        headers.update({
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        })
        
        try:
            # websockets 버전 호환성 문제 해결
            # 1. 버전에 따라 다른 방식으로 연결 시도
            try:
                # 방법 1: connect 함수에 헤더 전달 (최신 버전)
                self.websocket = await websockets.connect(
                    url, 
                    extra_headers=headers
                )
            except TypeError:
                # 방법 2: connect 함수에 헤더 전달하지 않음 (이전 버전)
                logger.info("이전 버전의 websockets 사용 - 헤더 설정 없이 연결 시도")
                # URL에 쿠키 정보 포함되어 있으므로 헤더 없이도 연결 가능할 수 있음
                self.websocket = await websockets.connect(url)
            
            self.is_connected = True
            logger.info("WebSocket 연결 완료 ✅")
            
            # 메시지 수신 작업 시작
            self.task = asyncio.create_task(self._receive_messages())
            
            return True
        except Exception as e:
            logger.error(f"연결 오류: {e}")
            
            # HTTP 403 오류 발생 시 추가 정보 제공
            if "403" in str(e):
                logger.error("HTTP 403 Forbidden 에러 발생: 인증 헤더가 올바르지 않거나 세션이 만료되었을 수 있습니다.")
                logger.error("새로운 세션 ID를 얻어 설정을 업데이트하세요.")
            
            self.is_connected = False
            return False
    
    async def disconnect(self) -> bool:
        """WebSocket 서버와의 연결 종료"""
        if not self.is_connected:
            return True
        
        try:
            if self.task and not self.task.done():
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass
            
            if self.websocket:
                await self.websocket.close()
                
            self.is_connected = False
            logger.info("WebSocket 연결 종료")
            return True
        except Exception as e:
            logger.error(f"Disconnect error: {e}")
            return False
    
    async def _receive_messages(self):
        """메시지 수신 루프"""
        try:
            while self.is_connected:
                try:
                    # 30초 타임아웃으로 메시지 수신 시도
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=30.0)
                    
                    try:
                        data = json.loads(message)
                        
                        # 메시지 처리
                        await self._process_message(data)
                        
                    except json.JSONDecodeError:
                        logger.warning(f"Received invalid JSON")
                        
                except asyncio.TimeoutError:
                    # 30초 동안 메시지 없음 - 연결 확인 메시지 전송
                    logger.debug("No messages received for 30 seconds, sending ping...")
                    try:
                        pong_waiter = await self.websocket.ping()
                        await asyncio.wait_for(pong_waiter, timeout=10.0)
                        logger.debug("Pong received, connection is still active")
                    except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                        logger.warning("Ping failed, connection seems to be lost")
                        # 연결이 끊어졌으므로 재연결 시도
                        self.is_connected = False
                        break
                    
        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"Connection closed by server: {e}")
            self.is_connected = False
            # 정상적인 종료가 아닌 경우 재연결 시도
            if e.code != 1000:  # 1000은 정상 종료
                await self._attempt_reconnect()
            
        except asyncio.CancelledError:
            logger.info("Message receiving task cancelled")
            raise
            
        except Exception as e:
            logger.error(f"Error in message receiving: {e}")
            self.is_connected = False
            await self._attempt_reconnect()
    
    async def _attempt_reconnect(self):
        """웹소켓 재연결 시도"""
        # 이미 최대 재시도 횟수를 초과한 경우
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"최대 재연결 시도 횟수({self.max_reconnect_attempts}회)를 초과했습니다. 재연결을 중단합니다.")
            return False
        
        # 마지막 재연결 시도 후 60초 이상 지났으면 재시도 횟수 초기화
        now = datetime.now()
        if (now - self.last_reconnect_attempt) > timedelta(seconds=60):
            self.reconnect_attempts = 0
        
        self.reconnect_attempts += 1
        self.last_reconnect_attempt = now
        
        # 백오프 지연 시간 계산 (1초, 2초, 4초...)
        delay = 2 ** (self.reconnect_attempts - 1)
        logger.info(f"재연결 시도 {self.reconnect_attempts}/{self.max_reconnect_attempts}... {delay}초 후 시도합니다.")
        
        await asyncio.sleep(delay)
        return await self.connect()
    
    async def _process_message(self, data: Dict[str, Any]):
        """수신된 메시지 처리"""
        try:
            msg_type = data.get("type", "unknown")
            
            # 디버깅용 로그 추가
            if msg_type == "lobby.historyUpdated" and "args" in data:
                logger.debug(f"수신 데이터 구조 유형: {type(data['args'])}")
                if isinstance(data['args'], dict) and len(data['args']) > 0:
                    first_key = next(iter(data['args']))
                    logger.debug(f"첫번째 테이블 데이터 구조: {type(data['args'][first_key])}")
                    if 'results' in data['args'][first_key]:
                        logger.debug(f"results 데이터 구조: {type(data['args'][first_key]['results'])}")
                        if len(data['args'][first_key]['results']) > 0:
                            logger.debug(f"첫번째 결과 예시: {data['args'][first_key]['results'][0]}")
            
            # 외부 콜백 호출 (있는 경우)
            if self.on_message_callback:
                await self.on_message_callback(data)
            
            # lobby.historyUpdated 메시지 처리
            if msg_type == "lobby.historyUpdated" and "args" in data:
                args = data["args"]
                if not isinstance(args, dict):
                    logger.warning(f"예상치 못한 args 데이터 형식: {type(args)}")
                    return
                    
                for table_id, table_data in args.items():
                    if not isinstance(table_data, dict) or "results" not in table_data:
                        logger.warning(f"테이블 {table_id}: 데이터 형식 오류 또는 결과 없음")
                        continue
                        
                    if not isinstance(table_data["results"], list):
                        logger.warning(f"테이블 {table_id}: 예상치 못한 results 데이터 형식: {type(table_data['results'])}")
                        continue
                    
                    # 결과가 비어있는 경우 건너뛰기
                    if not table_data["results"]:
                        continue
                        
                    # 결과 정렬 시도
                    try:
                        results = []
                        for item in table_data["results"]:
                            # pos 필드 확인
                            if "pos" not in item:
                                logger.warning(f"테이블 {table_id}: 'pos' 필드 없음: {item}")
                                continue
                                
                            pos = item["pos"]
                            if not isinstance(pos, (list, tuple)) or len(pos) < 2:
                                logger.warning(f"테이블 {table_id}: 잘못된 pos 형식: {pos}")
                                continue
                                
                            try:
                                # 정렬 키 계산 시도
                                sort_key = pos[0] * 7 + pos[1]
                                item["_sort_key"] = sort_key
                                results.append(item)
                            except (TypeError, IndexError) as e:
                                logger.warning(f"테이블 {table_id}: 정렬 키 계산 오류: {e}, pos={pos}")
                                continue
                        
                        # 정렬 수행
                        if results:
                            sorted_results = sorted(results, key=lambda x: x.get("_sort_key", 0))
                            # _sort_key 제거
                            for item in sorted_results:
                                if "_sort_key" in item:
                                    del item["_sort_key"]
                        else:
                            sorted_results = []
                            
                    except Exception as e:
                        logger.warning(f"테이블 {table_id}: 결과 정렬 중 오류 발생: {e}")
                        continue

                    display_name = self.room_mappings.get(table_id, table_id)

                    if self.filter_keywords:
                        matches_filter = any(keyword.lower() in display_name.lower() for keyword in self.filter_keywords)
                        if not matches_filter:
                            continue

                    # 기존 저장된 결과와 다를 때만 출력
                    if table_id not in self.received_tables or self.received_tables[table_id] != sorted_results:
                        self.received_tables[table_id] = sorted_results

                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"📩 방 ID: {table_id} (이름: {display_name}) 결과 수신: {len(sorted_results)}개")

                            # 최근 결과 5개 출력
                            recent_results = sorted_results[-5:] if len(sorted_results) >= 5 else sorted_results
                            for idx, item in enumerate(recent_results, start=len(sorted_results)-len(recent_results)+1):
                                try:
                                    x, y = item.get('pos', [0, 0])
                                    c = item.get('c', ' ')
                                    winner = "Banker(뱅커)" if c == 'R' else ("Player(플레이어)" if c == 'B' else "알수없음")
                                    
                                    # 승자 외 추가 정보 (nat, ties, pp, bp 등) 확인
                                    extras = []
                                    if item.get('nat') == 1:
                                        extras.append('Natural')
                                    if item.get('ties') == 1:
                                        extras.append('Tie')
                                    if item.get('pp') == 1:
                                        extras.append('Player Pair')
                                    if item.get('bp') == 1:
                                        extras.append('Banker Pair')

                                    extras_text = f" ({', '.join(extras)})" if extras else ""
                                    logger.debug(f"    {idx}번째 게임: pos=({x},{y}) → 승자={winner}{extras_text}")
                                except Exception as e:
                                    logger.warning(f"결과 로깅 중 오류: {e}, 데이터: {item}")
        
        except Exception as e:
            logger.error(f"메시지 처리 중 오류 발생: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

    async def detect_session_expiry(self, error_message: str) -> bool:
        """세션 만료 감지"""
        if "403 Forbidden" in error_message or "rejected WebSocket connection" in error_message:
            logger.warning("세션이 만료되었거나 유효하지 않습니다.")
            return True
        return False

    async def _attempt_reconnect(self):
        """웹소켓 재연결 시도"""
        # 이미 최대 재시도 횟수를 초과한 경우
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"최대 재연결 시도 횟수({self.max_reconnect_attempts}회)를 초과했습니다. 재연결을 중단합니다.")
            return False
        
        # 마지막 재연결 시도 후 60초 이상 지났으면 재시도 횟수 초기화
        now = datetime.now()
        if (now - self.last_reconnect_attempt) > timedelta(seconds=60):
            self.reconnect_attempts = 0
        
        self.reconnect_attempts += 1
        self.last_reconnect_attempt = now
        
        # 세션 만료 확인
        if self.reconnect_attempts >= 2:
            logger.warning("재연결 반복 실패: 세션이 만료되었을 수 있습니다.")
            # 여기서 세션 갱신 메커니즘 추가 가능
        
        # 백오프 지연 시간 계산 (1초, 2초, 4초...)
        delay = 2 ** (self.reconnect_attempts - 1)
        logger.info(f"재연결 시도 {self.reconnect_attempts}/{self.max_reconnect_attempts}... {delay}초 후 시도합니다.")
        
        await asyncio.sleep(delay)
        return await self.connect()
                         
class LobbyMonitor:
    """바카라 로비 모니터링 매니저"""
    
    def __init__(self):
        self.clients: Dict[str, Dict[str, Any]] = {}  # user_id -> {client, task, room_data}
        self.session_configs: Dict[str, ClientConfig] = {}  # user_id -> config
        self.streak_settings: Dict[str, Dict[str, Any]] = {}  # user_id -> settings
        self.room_mappings: Dict[str, Dict[str, str]] = {}  # user_id -> room_mappings
        self.connected_websockets: Dict[str, Set[WebSocket]] = {}  # user_id -> set of websockets
    
    def get_active_monitors_count(self) -> int:
        """활성 모니터링 수 반환"""
        return len([c for c in self.clients.values() if c.get('task') is not None])
    
    def has_session_config(self, user_id: str) -> bool:
        """사용자의 세션 설정 여부 확인"""
        return user_id in self.session_configs
    
    def has_user_data(self, user_id: str) -> bool:
        """사용자 데이터 존재 여부 확인"""
        return user_id in self.clients
    
    def is_client_running(self, user_id: str) -> bool:
        """클라이언트 실행 여부 확인"""
        return user_id in self.clients and self.clients[user_id].get('task') is not None
    
    def get_room_mappings(self, user_id: str) -> Dict[str, str]:
        """사용자별 방 매핑 반환"""
        if user_id in self.room_mappings:
            return self.room_mappings[user_id]
        
        # 기본 방 매핑 로드
        try:
            if os.path.exists("filtered_room_mappings.json"):
                with open("filtered_room_mappings.json", 'r', encoding='utf-8') as f:
                    mappings_config = json.load(f)
                    mappings = mappings_config.get("room_mappings", {})
                    self.room_mappings[user_id] = mappings
                    return mappings
            elif os.path.exists("room_mappings.json"):
                with open("room_mappings.json", 'r', encoding='utf-8') as f:
                    mappings_config = json.load(f)
                    mappings = mappings_config.get("room_mappings", {})
                    self.room_mappings[user_id] = mappings
                    return mappings
            
            # 파일이 없는 경우 빈 매핑 사용
            self.room_mappings[user_id] = {}
            return {}
        except Exception as e:
            logger.error(f"방 매핑 로드 오류: {e}")
            self.room_mappings[user_id] = {}
            return {}
    
    def set_room_mappings(self, user_id: str, mappings: Dict[str, str]):
        """사용자별 방 매핑 설정"""
        self.room_mappings[user_id] = mappings
    
    def set_session_config(self, user_id: str, config: ClientConfig):
        """세션 설정 저장"""
        self.session_configs[user_id] = config
    
    def set_streak_settings(self, user_id: str, settings: Dict[str, Any]):
        """연패 설정 저장"""
        self.streak_settings[user_id] = settings
    
    async def register_websocket(self, user_id: str, websocket: WebSocket):
        """웹소켓 연결 등록"""
        if user_id not in self.connected_websockets:
            self.connected_websockets[user_id] = set()
        
        await websocket.accept()
        self.connected_websockets[user_id].add(websocket)
        
        # 연결 즉시 현재 데이터 전송
        await self.send_init_data(user_id, websocket)
    
    def unregister_websocket(self, user_id: str, websocket: WebSocket):
        """웹소켓 연결 해제"""
        if user_id in self.connected_websockets:
            self.connected_websockets[user_id].discard(websocket)
    
    async def send_init_data(self, user_id: str, websocket: WebSocket):
        """초기 데이터 전송"""
        if user_id in self.clients:
            monitor_data = self.get_monitor_data(user_id)
            
            try:
                await websocket.send_json({
                    "type": "init_data",
                    "is_running": self.is_client_running(user_id),
                    "monitor_data": monitor_data
                })
            except Exception as e:
                logger.error(f"초기 데이터 전송 오류: {e}")
    
    async def broadcast_to_user(self, user_id: str, message: dict):
        """특정 사용자의 모든 웹소켓 연결에 메시지 전송"""
        if user_id not in self.connected_websockets:
            return
        
        dead_sockets = set()
        for websocket in self.connected_websockets[user_id]:
            try:
                await websocket.send_json(message)
            except Exception:
                dead_sockets.add(websocket)
        
        # 끊어진 소켓 제거
        for dead_socket in dead_sockets:
            self.connected_websockets[user_id].discard(dead_socket)
            
    def get_monitor_data(self, user_id: str) -> Dict[str, Any]:
        """모니터링 데이터 반환"""
        if user_id not in self.clients:
            return {"streak_data": {"player_streak_rooms": [], "banker_streak_rooms": []}}
        
        room_data = self.clients[user_id].get('room_data', {})
        streak_data = self.calculate_streaks(user_id, room_data)
        
        return {
            "streak_data": streak_data
        }
    
    def get_room_data(self, user_id: str, room_id: str) -> Optional[List[Dict[str, Any]]]:
        """특정 방의 데이터 반환"""
        if user_id not in self.clients or 'room_data' not in self.clients[user_id]:
            return None
        
        return self.clients[user_id]['room_data'].get(room_id)
    
    def calculate_streaks(self, user_id: str, room_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """연패 데이터 계산"""
        if user_id not in self.streak_settings:
            # 기본 설정 사용
            self.streak_settings[user_id] = {
                "player_streak": 3,  # 플레이어 연패 기준
                "banker_streak": 3,  # 뱅커 연패 기준
                "min_results": 10,   # 최소 결과 수
            }
        
        settings = self.streak_settings[user_id]
        room_mappings = self.get_room_mappings(user_id)
        
        streak_rooms = {
            "player_streak_rooms": [],  # 플레이어 연패 중인 방
            "banker_streak_rooms": [],  # 뱅커 연패 중인 방
            "updated_at": datetime.now().isoformat()
        }
        
        try:
            for room_id, results in room_data.items():
                # 최소 결과 수 미만인 방은 무시
                if len(results) < settings["min_results"]:
                    continue
                
                try:
                    # 결과 정렬 함수
                    def get_sort_key(result):
                        try:
                            pos = result.get("pos", [0, 0])
                            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                                return pos[0] * 7 + pos[1]
                            return 0
                        except Exception:
                            return 0
                    
                    # 시간순 정렬 (오래된 것부터 최신까지)
                    sorted_results = sorted(results, key=get_sort_key)
                    
                    # 플레이어(B)/뱅커(R) 연속 횟수 계산
                    player_streak = 0
                    banker_streak = 0
                    
                    # 결과 역순 (최신부터 오래된 순)으로 연속성 계산
                    for result in reversed(sorted_results):
                        # 'c' 필드가 없는 경우 건너뛰기
                        if 'c' not in result:
                            continue
                            
                        c = result.get('c', '')
                        
                        if c == 'B':  # 플레이어 승리
                            player_streak += 1
                            banker_streak = 0  # 뱅커 연속 초기화
                        elif c == 'R':  # 뱅커 승리
                            banker_streak += 1
                            player_streak = 0  # 플레이어 연속 초기화
                        else:
                            # 타이 등 다른 결과는 연속 횟수 초기화
                            player_streak = 0
                            banker_streak = 0
                        
                        # 일정 횟수 이상 확인되면 루프 종료
                        if player_streak >= settings["player_streak"] or banker_streak >= settings["banker_streak"]:
                            break
                    
                    # 최근 게임 결과 문자열 생성 (최신 15개)
                    recent_count = min(15, len(sorted_results))
                    recent_results = sorted_results[-recent_count:]
                    result_pattern = "".join([
                        "P" if r.get('c', '') == 'B' else 
                        ("B" if r.get('c', '') == 'R' else "T") 
                        for r in recent_results
                    ])
                    
                    room_name = room_mappings.get(room_id, room_id)
                    
                    # 디버깅 로그 추가
                    logger.debug(f"방 {room_id} ({room_name}) - 패턴: {result_pattern}, " 
                                f"P연속: {player_streak}, B연속: {banker_streak}")
                    
                    # 플레이어 연승 중인 방 (P가 연속으로 이김)
                    if player_streak >= settings["player_streak"]:
                        streak_rooms["player_streak_rooms"].append({
                            "room_id": room_id,
                            "room_name": room_name,
                            "streak": player_streak,
                            "recent_pattern": result_pattern
                        })
                    
                    # 뱅커 연승 중인 방 (B가 연속으로 이김)
                    if banker_streak >= settings["banker_streak"]:
                        streak_rooms["banker_streak_rooms"].append({
                            "room_id": room_id,
                            "room_name": room_name,
                            "streak": banker_streak,
                            "recent_pattern": result_pattern
                        })
                except Exception as e:
                    logger.warning(f"방 {room_id} 연속 패턴 계산 오류: {e}")
                    import traceback
                    logger.warning(traceback.format_exc())
                    continue
            
            # 연패 횟수 기준 내림차순 정렬
            streak_rooms["player_streak_rooms"].sort(key=lambda x: x["streak"], reverse=True)
            streak_rooms["banker_streak_rooms"].sort(key=lambda x: x["streak"], reverse=True)
            
        except Exception as e:
            logger.error(f"연패 데이터 계산 중 오류 발생: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return streak_rooms

    async def recalculate_streaks(self, user_id: str):
        """연패 데이터 재계산 및 전송"""
        if user_id not in self.clients or 'room_data' not in self.clients[user_id]:
            return
        
        room_data = self.clients[user_id]['room_data']
        streak_data = self.calculate_streaks(user_id, room_data)
        
        # 웹소켓으로 데이터 전송
        await self.broadcast_to_user(user_id, {
            "type": "data_update",
            "streak_data": streak_data
        })
    
    async def recalculate_predictions(self, user_id: str):
        """예측 데이터 재계산 및 전송"""
        # 실제 구현은 prediction_engine와 연동 필요
        pass
    
    async def start_client(self, user_id: str, prediction_engine=None) -> bool:
        """바카라 클라이언트 시작"""
        if user_id not in self.session_configs:
            logger.error(f"사용자 {user_id}의 세션 설정이 없습니다.")
            return False
        
        if user_id in self.clients and self.clients[user_id].get('task') is not None:
            logger.info(f"사용자 {user_id}의 클라이언트가 이미 실행 중입니다.")
            return True
        
        config = self.session_configs[user_id]
        room_mappings = self.get_room_mappings(user_id)
        
        # 사용자별 데이터 저장소 초기화
        if user_id not in self.clients:
            self.clients[user_id] = {
                'client': None,
                'task': None,
                'room_data': {}
            }
        
        # 기존 태스크 종료
        if self.clients[user_id].get('task') is not None:
            self.clients[user_id]['task'].cancel()
            try:
                await self.clients[user_id]['task']
            except asyncio.CancelledError:
                pass
        
        # 클라이언트 연결 종료
        if self.clients[user_id].get('client') is not None:
            await self.clients[user_id]['client'].disconnect()
        
        # 메시지 처리 콜백 함수
        async def on_message_callback(data: Dict[str, Any]):
            msg_type = data.get("type", "unknown")
            
            # 디버깅 로그 추가 - 데이터 구조 이해 (안전하게 수정)
            if msg_type == "lobby.historyUpdated" and "args" in data:
                logger.debug(f"데이터 유형: {msg_type}, args 타입: {type(data['args'])}")
                try:
                    # 데이터 구조 샘플 로깅
                    if isinstance(data["args"], dict) and data["args"]:
                        first_key = next(iter(data["args"]))
                        first_item = data["args"][first_key]
                        logger.debug(f"첫 번째 항목 키: {first_key}, 값 타입: {type(first_item)}")
                        if isinstance(first_item, dict) and "results" in first_item:
                            logger.debug(f"results 타입: {type(first_item['results'])}")
                            if first_item["results"] and len(first_item["results"]) > 0:
                                first_result = first_item["results"][0]
                                logger.debug(f"첫 번째 결과 구조: {first_result}")
                                if isinstance(first_result, dict):
                                    pos_value = first_result.get('pos', None)
                                    logger.debug(f"pos 필드 타입: {type(pos_value)}")
                                else:
                                    logger.debug(f"첫 번째 결과가 딕셔너리가 아님: {type(first_result)}")
                except Exception as e:
                    logger.warning(f"디버깅 로그 생성 중 오류 (무시됨): {e}")
            
            # 방 데이터 업데이트 처리
            if msg_type == "lobby.historyUpdated" and "args" in data:
                try:
                    args = data["args"]
                    updates = False
                    
                    if not isinstance(args, dict):
                        logger.warning(f"예상치 못한 args 타입: {type(args)}")
                        return
                    
                    # 허용된 방 목록 가져오기 (여기에 필터링 로직 추가됨)
                    room_mappings = self.get_room_mappings(user_id)
                    allowed_room_ids = set(room_mappings.keys())
                    
                    # 허용된 방 있을 때 로그
                    if allowed_room_ids:
                        logger.info(f"필터링 모드 활성화: {len(allowed_room_ids)}개 방만 모니터링")
                    
                    for table_id, table_data in args.items():
                        # filtered_room_mappings.json에 있는 방만 처리 (핵심 필터링 로직)
                        if allowed_room_ids and table_id not in allowed_room_ids:
                            continue  # 허용 목록에 없는 방은 건너뛰기
                        
                        if not isinstance(table_data, dict) or "results" not in table_data:
                            logger.warning(f"테이블 {table_id}: 잘못된 데이터 구조 또는 results 없음")
                            continue
                            
                        results_data = table_data["results"]
                        if not isinstance(results_data, list):
                            logger.warning(f"테이블 {table_id}: results가 리스트가 아님: {type(results_data)}")
                            continue
                        
                        # 결과 정렬 시도 (안전한 방식으로)
                        try:
                            processed_results = []
                            
                            for item in results_data:
                                # 각 항목이 딕셔너리인지 확인
                                if not isinstance(item, dict):
                                    logger.warning(f"테이블 {table_id}: 결과 항목이 딕셔너리가 아님: {type(item)}")
                                    continue
                                    
                                # pos 필드 안전하게 추출
                                pos = item.get("pos")
                                
                                # pos 필드 형식 검증
                                valid_pos = False
                                sort_key = 0
                                
                                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                                    # 리스트/튜플 형식의 pos
                                    try:
                                        sort_key = pos[0] * 7 + pos[1]
                                        valid_pos = True
                                    except (TypeError, IndexError):
                                        pass
                                elif isinstance(pos, dict) and 'x' in pos and 'y' in pos:
                                    # 딕셔너리 형식의 pos (x, y 키 사용)
                                    try:
                                        sort_key = pos['x'] * 7 + pos['y']
                                        valid_pos = True
                                    except (TypeError, KeyError):
                                        pass
                                elif isinstance(pos, str) and ',' in pos:
                                    # 문자열 형식의 pos ("x,y")
                                    try:
                                        x, y = map(int, pos.split(','))
                                        sort_key = x * 7 + y
                                        valid_pos = True
                                    except (ValueError, TypeError):
                                        pass
                                elif isinstance(pos, int):
                                    # 정수 형식의 pos (이미 계산된 값)
                                    sort_key = pos
                                    valid_pos = True
                                
                                if valid_pos:
                                    # 정렬을 위한 임시 키 추가
                                    item_copy = item.copy()
                                    item_copy["_sort_key"] = sort_key
                                    processed_results.append(item_copy)
                                else:
                                    logger.warning(f"테이블 {table_id}: 지원되지 않는 pos 형식: {pos}")
                            
                            if processed_results:
                                # 정렬 및 임시 키 제거
                                results = sorted(processed_results, key=lambda x: x.get("_sort_key", 0))
                                for r in results:
                                    if "_sort_key" in r:
                                        del r["_sort_key"]
                            else:
                                # 처리된 결과가 없으면 원본 그대로 사용
                                results = results_data
                                
                        except Exception as e:
                            logger.warning(f"테이블 {table_id}: 결과 정렬 실패: {str(e)}")
                            # 정렬 실패 시 원본 데이터 사용
                            results = results_data
                        
                        # 방 데이터 업데이트
                        self.clients[user_id]['room_data'][table_id] = results
                        updates = True
                    
                    # 연패 데이터 계산 및 브로드캐스트
                    if updates:
                        room_data = self.clients[user_id]['room_data']
                        streak_data = self.calculate_streaks(user_id, room_data)
                        
                        # 웹소켓으로 데이터 전송
                        await self.broadcast_to_user(user_id, {
                            "type": "data_update",
                            "streak_data": streak_data
                        })
                        
                except Exception as e:
                    logger.error(f"메시지 처리 중 오류: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
                    
       
        # 클라이언트 생성
        client = BaccaratWebSocketClient(
            config=config,
            room_mappings=room_mappings,
            filter_keywords=[],  # 필터링 비활성화 - 모든 데이터 수집
            on_message_callback=on_message_callback
        )
        
        # 클라이언트 연결
        connected = await client.connect()
        if not connected:
            logger.error(f"사용자 {user_id}의 바카라 서버 연결 실패")
            return False
        
        # 클라이언트 실행 태스크
        async def run_client():
            try:
                logger.info(f"사용자 {user_id}의 바카라 클라이언트 시작")
                
                # 클라이언트 상태 업데이트 전송
                await self.broadcast_to_user(user_id, {
                    "type": "status_update",
                    "is_running": True
                })
                
                # 클라이언트 연결 유지
                while client.is_connected:
                    await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                logger.info(f"사용자 {user_id}의 바카라 클라이언트 작업이 취소되었습니다.")
                raise
            except Exception as e:
                logger.error(f"사용자 {user_id}의 바카라 클라이언트 오류: {e}")
            finally:
                await client.disconnect()
                
                # 클라이언트 상태 업데이트 전송
                await self.broadcast_to_user(user_id, {
                    "type": "status_update",
                    "is_running": False
                })
                
                logger.info(f"사용자 {user_id}의 바카라 클라이언트 종료")
                
                # 태스크 참조 제거
                if user_id in self.clients:
                    self.clients[user_id]['task'] = None
        
        # 클라이언트 및 태스크 저장
        self.clients[user_id]['client'] = client
        self.clients[user_id]['task'] = asyncio.create_task(run_client())
        
        return True
    
    async def stop_client(self, user_id: str) -> bool:
        """바카라 클라이언트 중지"""
        if user_id not in self.clients or self.clients[user_id].get('task') is None:
            logger.info(f"사용자 {user_id}의 클라이언트가 실행 중이 아닙니다.")
            return False
        
        # 태스크 종료
        self.clients[user_id]['task'].cancel()
        try:
            await self.clients[user_id]['task']
        except asyncio.CancelledError:
            pass
        
        # 클라이언트 연결 종료
        if self.clients[user_id].get('client') is not None:
            await self.clients[user_id]['client'].disconnect()
        
        # 상태 업데이트
        self.clients[user_id]['task'] = None
        self.clients[user_id]['client'] = None
        
        return True
    
    # LobbyMonitor 클래스에 추가할 메서드
    def set_session_config_from_url(self, user_id: str, ws_url: str) -> bool:
        """URL에서 세션 설정 추출하여 저장"""
        # utils/url_extractor.py의 메서드 사용
        from utils.url_extractor import URLExtractor
        
        config_data = URLExtractor.extract_baccarat_config(ws_url)
        if not config_data:
            return False
        
        config = ClientConfig(
            session_id=config_data["session_id"],
            bare_session_id=config_data["bare_session_id"],
            instance=config_data["instance"],
            client_version=config_data["client_version"],
            domain=config_data.get("domain", "skylinestart.evo-games.com"),
            protocol=config_data.get("protocol", "wss")
        )
        
        self.session_configs[user_id] = config
        return True