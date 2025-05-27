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
        self.domain = domain or "skylinestart.evo-games.com"
        self.protocol = protocol or "wss"
    
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
                 on_message_callback: callable = None):
        self.config = config
        self.websocket = None
        self.is_connected = False
        self.task = None
        self.received_tables: Dict[str, Any] = {}
        self.last_reconnect_attempt = datetime.now()
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3
        
        # 방 이름 매핑 설정
        self.room_mappings = room_mappings or {}
        
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
        
        headers.update({
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        })
        
        try:
            try:
                self.websocket = await websockets.connect(url, extra_headers=headers)
            except TypeError:
                logger.info("이전 버전의 websockets 사용 - 헤더 설정 없이 연결 시도")
                self.websocket = await websockets.connect(url)
            
            self.is_connected = True
            logger.info("WebSocket 연결 완료 ✅")
            
            # 메시지 수신 작업 시작
            self.task = asyncio.create_task(self._receive_messages())
            
            return True
        except Exception as e:
            logger.error(f"연결 오류: {e}")
            
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
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=30.0)
                    
                    try:
                        data = json.loads(message)
                        await self._process_message(data)
                        
                    except json.JSONDecodeError:
                        logger.warning(f"Received invalid JSON")
                        
                except asyncio.TimeoutError:
                    logger.debug("No messages received for 30 seconds, sending ping...")
                    try:
                        pong_waiter = await self.websocket.ping()
                        await asyncio.wait_for(pong_waiter, timeout=10.0)
                        logger.debug("Pong received, connection is still active")
                    except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                        logger.warning("Ping failed, connection seems to be lost")
                        self.is_connected = False
                        break
                    
        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"Connection closed by server: {e}")
            self.is_connected = False
            if e.code != 1000: 
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
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"최대 재연결 시도 횟수({self.max_reconnect_attempts}회)를 초과했습니다. 재연결을 중단합니다.")
            return False
        
        now = datetime.now()
        if (now - self.last_reconnect_attempt) > timedelta(seconds=60):
            self.reconnect_attempts = 0
        
        self.reconnect_attempts += 1
        self.last_reconnect_attempt = now
        
        delay = 2 ** (self.reconnect_attempts - 1)
        logger.info(f"재연결 시도 {self.reconnect_attempts}/{self.max_reconnect_attempts}... {delay}초 후 시도합니다.")
        
        await asyncio.sleep(delay)
        return await self.connect()
    
    async def _process_message(self, data: Dict[str, Any]):
        """수신된 메시지 처리 (바카라 방만 필터링)"""
        try:
            msg_type = data.get("type", "unknown")
            
            # 외부 콜백 호출 (있는 경우)
            if self.on_message_callback:
                await self.on_message_callback(data)
            
            # lobby.historyUpdated 메시지 처리 (바카라 방만)
            if msg_type == "lobby.historyUpdated" and "args" in data:
                args = data["args"]
                if not isinstance(args, dict):
                    return
                    
                for table_id, table_data in args.items():
                    # **바카라 방만 처리 - room_mappings에 있는 방만**
                    if table_id not in self.room_mappings:
                        continue  # 등록되지 않은 방은 건너뛰기
                    
                    if not isinstance(table_data, dict) or "results" not in table_data:
                        continue
                        
                    results = table_data["results"]
                    if not isinstance(results, list) or not results:
                        continue
                        
                    # 바카라 데이터 검증 및 정렬
                    try:
                        sorted_results = []
                        for item in results:
                            if not isinstance(item, dict):
                                continue
                            
                            # 바카라 결과에 필수적인 필드 확인
                            if 'c' not in item or item.get('c') not in ['B', 'R', 'T']:
                                continue
                            
                            # pos 필드 확인 및 검증
                            pos = item.get("pos")
                            if not isinstance(pos, (list, tuple)) or len(pos) < 2:
                                continue
                            
                            # 정렬 키 계산
                            try:
                                if isinstance(pos[0], (int, float)) and isinstance(pos[1], (int, float)):
                                    sort_key = pos[0] * 7 + pos[1]
                                    item["_sort_key"] = sort_key
                                    sorted_results.append(item)
                            except (TypeError, IndexError):
                                continue
                        
                        # 정렬 수행
                        if sorted_results:
                            sorted_results = sorted(sorted_results, key=lambda x: x.get("_sort_key", 0))
                            # _sort_key 제거
                            for item in sorted_results:
                                if "_sort_key" in item:
                                    del item["_sort_key"]
                        else:
                            continue  # 유효한 바카라 결과가 없으면 건너뛰기
                            
                    except Exception:
                        continue  # 정렬 실패 시 건너뛰기

                    display_name = self.room_mappings.get(table_id, table_id)

                    # 기존 저장된 결과와 다를 때만 저장
                    if table_id not in self.received_tables or self.received_tables[table_id] != sorted_results:
                        self.received_tables[table_id] = sorted_results

                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"📩 방 ID: {table_id} (이름: {display_name}) 결과 수신: {len(sorted_results)}개")
        
        except Exception as e:
            logger.debug(f"메시지 처리 중 오류 발생 (무시됨): {str(e)}")


class LobbyMonitor:
    """바카라 로비 모니터링 매니저 (예측픽 제거 버전)"""
    
    def __init__(self):
        self.clients: Dict[str, Dict[str, Any]] = {}  # user_id -> {client, task, room_data}
        self.session_configs: Dict[str, ClientConfig] = {}  # user_id -> config
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
        """모니터링 데이터 반환 (필터링된 방만)"""
        if user_id not in self.clients:
            return {"filtered_rooms": []}
        
        room_data = self.clients[user_id].get('room_data', {})
        filtered_data = self.get_filtered_room_data(user_id, room_data)
        
        return {
            "filtered_rooms": filtered_data,
            "total_rooms": len(filtered_data),
            "updated_at": datetime.now().isoformat()
        }
    
    def get_filtered_room_data(self, user_id: str, room_data: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """필터링된 방 데이터 반환 (바카라 전용)"""
        room_mappings = self.get_room_mappings(user_id)
        filtered_rooms = []
        
        try:
            for room_id, results in room_data.items():
                # filtered_room_mappings.json에 있는 바카라 방만 처리
                if room_id not in room_mappings:
                    continue
                
                if not isinstance(results, list) or not results:
                    continue
                
                # 바카라 게임 결과인지 검증
                valid_baccarat_results = []
                for result in results:
                    if (isinstance(result, dict) and 
                        'c' in result and  # 바카라 승부 결과 필드
                        result.get('c') in ['B', 'R', 'T']):  # Player, Banker, Tie만 허용
                        valid_baccarat_results.append(result)
                
                # 유효한 바카라 결과가 없으면 건너뛰기
                if not valid_baccarat_results:
                    continue
                
                # 결과 정렬
                try:
                    def get_sort_key(result):
                        try:
                            pos = result.get("pos", [0, 0])
                            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                                if isinstance(pos[0], (int, float)) and isinstance(pos[1], (int, float)):
                                    return pos[0] * 7 + pos[1]
                            return 0
                        except Exception:
                            return 0
                    
                    sorted_results = sorted(valid_baccarat_results, key=get_sort_key)
                    
                    # 게임 결과 패턴 생성 (P=Player, B=Banker, T=Tie)
                    result_pattern = []
                    for result in sorted_results:
                        c = result.get('c', '')
                        if c == 'B':  # Player 승리
                            result_pattern.append('P')
                        elif c == 'R':  # Banker 승리
                            result_pattern.append('B')
                        else:  # Tie 또는 기타
                            result_pattern.append('T')
                    
                    # 최소 게임 수 체크 (너무 적은 게임은 제외)
                    if len(result_pattern) < 2:
                        continue
                    
                    room_info = {
                        "room_id": room_id,
                        "room_name": room_mappings.get(room_id, room_id),
                        "total_games": len(sorted_results),
                        "result_pattern": "".join(result_pattern),
                        "recent_15": "".join(result_pattern[-15:]) if len(result_pattern) >= 15 else "".join(result_pattern)
                    }
                    
                    filtered_rooms.append(room_info)
                
                except Exception as e:
                    logger.debug(f"방 {room_id} 데이터 처리 중 오류, 건너뛰기: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"필터링된 방 데이터 생성 중 오류: {e}")
        
        # 방 이름 순으로 정렬
        filtered_rooms.sort(key=lambda x: x["room_name"])
        
        return filtered_rooms
    
    def get_room_data(self, user_id: str, room_id: str) -> Optional[List[Dict[str, Any]]]:
        """특정 방의 데이터 반환"""
        if user_id not in self.clients or 'room_data' not in self.clients[user_id]:
            return None
        
        return self.clients[user_id]['room_data'].get(room_id)
    
    async def start_client(self, user_id: str) -> bool:
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
            
            # 방 데이터 업데이트 처리
            if msg_type == "lobby.historyUpdated" and "args" in data:
                try:
                    args = data["args"]
                    updates = False
                    
                    if not isinstance(args, dict):
                        logger.warning(f"예상치 못한 args 타입: {type(args)}")
                        return
                    
                    # 허용된 방 목록 가져오기 (바카라 방만 필터링)
                    room_mappings = self.get_room_mappings(user_id)
                    allowed_room_ids = set(room_mappings.keys())
                    
                    # 로그 레벨 조정 - 디버그 모드일 때만 출력
                    if logger.isEnabledFor(logging.DEBUG) and allowed_room_ids:
                        logger.debug(f"바카라 방 필터링 모드 활성화: {len(allowed_room_ids)}개 방만 모니터링")
                    
                    for table_id, table_data in args.items():
                        # **핵심 필터링: filtered_room_mappings.json에 있는 방만 처리**
                        if not allowed_room_ids or table_id not in allowed_room_ids:
                            continue  # 등록되지 않은 방은 무조건 건너뛰기
                        
                        if not isinstance(table_data, dict) or "results" not in table_data:
                            continue
                            
                        results_data = table_data["results"]
                        if not isinstance(results_data, list) or not results_data:
                            continue
                        
                        # 결과 정렬 (안전한 방식으로)
                        try:
                            processed_results = []
                            
                            for item in results_data:
                                # 바카라 게임 데이터 검증
                                if not isinstance(item, dict):
                                    # 딕셔너리가 아닌 경우는 바카라 게임이 아니므로 건너뛰기
                                    continue
                                
                                # 바카라 결과에 필수적인 필드 확인
                                if 'c' not in item:  # 바카라 승부 결과 필드가 없으면 건너뛰기
                                    continue
                                    
                                pos = item.get("pos")
                                valid_pos = False
                                sort_key = 0
                                
                                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                                    try:
                                        # pos 값이 숫자인지 확인
                                        if isinstance(pos[0], (int, float)) and isinstance(pos[1], (int, float)):
                                            sort_key = pos[0] * 7 + pos[1]
                                            valid_pos = True
                                    except (TypeError, IndexError):
                                        pass
                                
                                if valid_pos:
                                    item_copy = item.copy()
                                    item_copy["_sort_key"] = sort_key
                                    processed_results.append(item_copy)
                            
                            # 유효한 바카라 결과가 없으면 이 테이블은 건너뛰기
                            if not processed_results:
                                continue
                            
                            # 정렬 및 임시 키 제거
                            results = sorted(processed_results, key=lambda x: x.get("_sort_key", 0))
                            for r in results:
                                if "_sort_key" in r:
                                    del r["_sort_key"]
                                
                        except Exception as e:
                            # 정렬 실패 시 이 테이블은 건너뛰기
                            logger.debug(f"테이블 {table_id}: 결과 정렬 실패, 건너뛰기: {str(e)}")
                            continue
                        
                        # 방 데이터 업데이트
                        self.clients[user_id]['room_data'][table_id] = results
                        updates = True
                    
                    # 필터링된 데이터 브로드캐스트
                    if updates:
                        room_data = self.clients[user_id]['room_data']
                        filtered_data = self.get_filtered_room_data(user_id, room_data)
                        
                        # 간단한 출력 (콘솔)
                        if filtered_data:
                            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 📊 방 상태 업데이트:")
                            for room in filtered_data:
                                print(f"  {room['room_name']}: {room['total_games']}게임 | 최근15: {room['recent_15']}")
                        
                        # 웹소켓으로 데이터 전송
                        await self.broadcast_to_user(user_id, {
                            "type": "data_update",
                            "filtered_rooms": filtered_data,
                            "total_rooms": len(filtered_data)
                        })
                        
                except Exception as e:
                    logger.error(f"메시지 처리 중 오류: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
       
        # 클라이언트 생성
        client = BaccaratWebSocketClient(
            config=config,
            room_mappings=room_mappings,
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
    
    def set_session_config_from_url(self, user_id: str, ws_url: str) -> bool:
        """URL에서 세션 설정 추출하여 저장"""
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

    def print_filtered_rooms_summary(self, user_id: str):
        """필터링된 방 요약 정보 출력"""
        if user_id not in self.clients or 'room_data' not in self.clients[user_id]:
            print("❌ 사용자 데이터가 없습니다.")
            return
        
        room_data = self.clients[user_id]['room_data']
        filtered_data = self.get_filtered_room_data(user_id, room_data)
        
        if not filtered_data:
            print("📝 필터링된 방이 없습니다.")
            return
        
        print(f"\n📊 현재 모니터링 중인 방 ({len(filtered_data)}개):")
        print("=" * 60)
        
        for idx, room in enumerate(filtered_data, 1):
            print(f"{idx:2d}. {room['room_name']} ({room['room_id']})")
            print(f"    게임 수: {room['total_games']}개")
            print(f"    전체 패턴: {room['result_pattern']}")
            print(f"    최근 10게임: {room['recent_10']}")
            print(f"    {'=' * 50}")
        
        print(f"\n📈 패턴 범례: P=Player 승, B=Banker 승, T=Tie")
        print(f"🕐 업데이트 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")