import asyncio
import websockets
import json
import logging
from typing import Dict, Any, Optional, List
import sys
from datetime import datetime, timedelta
import os

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("baccarat_client")

class BaccaratWebSocketClient:
    """바카라 WebSocket 클라이언트 클래스"""
    
    def __init__(self, session_id: str, bare_session_id: str, instance: str, client_version: str, 
                 room_mappings: Dict[str, str] = None, filter_keywords: List[str] = None):
        """
        바카라 WebSocket 클라이언트 초기화
        
        Args:
            session_id: 세션 ID (EVOSESSIONID)
            bare_session_id: 순수 세션 ID
            instance: 인스턴스 정보
            client_version: 클라이언트 버전
            room_mappings: 방 ID와 디스플레이 이름 매핑
            filter_keywords: 필터링할 키워드 목록
        """
        self.session_id = session_id
        self.bare_session_id = bare_session_id
        self.instance = instance
        self.client_version = client_version
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
        
    def _build_websocket_url(self) -> str:
        """WebSocket URL 생성"""
        return (
            f"wss://skylinestart.evo-games.com/public/lobby/socket/v2/{self.bare_session_id}"
            f"?messageFormat=json"
            f"&device=Desktop"
            f"&features=opensAt%2CmultipleHero%2CshortThumbnails%2CskipInfosPublished%2Csmc%2CuniRouletteHistory%2CbacHistoryV2%2Cfilters%2CtableDecorations"
            f"&instance={self.instance}-{self.bare_session_id}-"
            f"&EVOSESSIONID={self.session_id}"
            f"&client_version={self.client_version}"
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
            "Origin": "https://skylinestart.evo-games.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Cookie": f"EVOSESSIONID={self.session_id}"
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
                logger.error("새로운 세션 ID를 얻어 설정을 업데이트하세요: python session_manager.py --update")
            
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
                        
                        # 메시지 처리 - 불필요한 디버그 로깅 제거
                        await self._process_message(data)
                        
                    except json.JSONDecodeError:
                        logger.warning(f"Received invalid JSON")
                        
                except asyncio.TimeoutError:
                    # 30초 동안 메시지 없음 - 연결 확인 메시지 전송
                    logger.info("No messages received for 30 seconds, sending ping...")
                    try:
                        pong_waiter = await self.websocket.ping()
                        await asyncio.wait_for(pong_waiter, timeout=10.0)
                        logger.info("Pong received, connection is still active")
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
        msg_type = data.get("type", "unknown")

        # lobby.historyUpdated 메시지 처리
        if msg_type == "lobby.historyUpdated" and "args" in data:
            args = data["args"]
            for table_id, table_data in args.items():
                if "results" in table_data:
                    if table_id not in self.room_mappings:
                        continue

                    # 결과 정렬: x*7 + y 기준
                    results = sorted(
                        table_data["results"],
                        key=lambda item: item["pos"][0] * 7 + item["pos"][1]
                    )

                    display_name = self.room_mappings.get(table_id, table_id)

                    if self.filter_keywords:
                        matches_filter = any(keyword.lower() in display_name.lower() for keyword in self.filter_keywords)
                        if not matches_filter:
                            continue

                    # 기존 저장된 결과와 다를 때만 출력
                    if table_id not in self.received_tables or self.received_tables[table_id] != results:
                        self.received_tables[table_id] = results

                        logger.info(f"📩 방 ID: {table_id} (이름: {display_name}) 결과 수신:")

                        for idx, item in enumerate(results, start=1):
                            x, y = item['pos']
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
                            logger.info(f"    {idx:>3}번째 게임: pos=({x},{y}) → 승자={winner}{extras_text}")

async def run_client(config: Dict[str, str]):
    """클라이언트 실행"""
    # 방 매핑 설정 로드
    room_mappings = {}
    filter_keywords = []
    
    try:
        # 먼저 filtered_room_mappings.json 파일 확인
        if os.path.exists("filtered_room_mappings.json"):
            logger.info("💼 필터링된 방 매핑 파일(filtered_room_mappings.json)을 사용합니다.")
            with open("filtered_room_mappings.json", 'r', encoding='utf-8') as f:
                mappings_config = json.load(f)
                room_mappings = mappings_config.get("room_mappings", {})
                # 필터링된 매핑 파일에는 모든 방이 이미 필터링되었으므로 키워드는 비워둡니다
                filter_keywords = []
                
                logger.info(f"📋 총 {len(room_mappings)}개의 방 매핑 정보가 로드되었습니다.")
                # 처음 5개 매핑 정보 표시
                count = 0
                for room_id, name in list(room_mappings.items())[:5]:
                    logger.info(f"   {room_id}: {name}")
                    count += 1
                if len(room_mappings) > 5:
                    logger.info(f"   ... 외 {len(room_mappings) - 5}개")
                
        # 기본 room_mappings.json 파일 확인
        elif os.path.exists("room_mappings.json"):
            with open("room_mappings.json", 'r', encoding='utf-8') as f:
                mappings_config = json.load(f)
                room_mappings = mappings_config.get("room_mappings", {})
                filter_keywords = mappings_config.get("filter_keywords", [])
                
                if filter_keywords:
                    logger.info(f"필터 키워드: {', '.join(filter_keywords)}")
                    logger.info(f"키워드가 포함된 방만 표시됩니다.")
    except Exception as e:
        logger.warning(f"방 매핑 설정 로드 중 오류: {e}")
    
    client = BaccaratWebSocketClient(
        session_id=config["session_id"],
        bare_session_id=config["bare_session_id"],
        instance=config["instance"],
        client_version=config["client_version"],
        room_mappings=room_mappings,
        filter_keywords=filter_keywords
    )
    
    try:
        # 연결 시도
        connected = await client.connect()
        if not connected:
            logger.error("WebSocket connection failed")
            return
        
        # 연결이 유지되는 동안 실행
        while client.is_connected:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Program interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        # 연결 종료
        await client.disconnect()
        logger.info("Client stopped")

def load_config(config_file: str = "config.json") -> Dict[str, str]:
    """설정 파일 로드"""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Config file '{config_file}' not found")
        sys.exit(1)
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON format in config file '{config_file}'")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        sys.exit(1)