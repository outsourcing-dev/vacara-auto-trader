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
logger = logging.getLogger("bet_executor")

class RoomWebSocketClient:
    """바카라 방 WebSocket 클라이언트 클래스"""
    
    def __init__(self, room_ws_url: str, on_message_callback: callable = None):
        """
        바카라 방 WebSocket 클라이언트 초기화
        
        Args:
            room_ws_url: 방 WebSocket URL
            on_message_callback: 메시지 수신 시 호출할 콜백 함수
        """
        self.room_ws_url = room_ws_url
        self.websocket = None
        self.is_connected = False
        self.task = None
        self.last_reconnect_attempt = datetime.now()
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3
        
        # 콜백 함수
        self.on_message_callback = on_message_callback
        
    async def connect(self) -> bool:
        """WebSocket 서버에 연결"""
        if self.is_connected:
            logger.warning("Already connected")
            return True
        
        logger.info(f"방 WebSocket 서버에 연결 중...")
        
        # 브라우저와 동일한 인증 헤더 설정
        headers = {
            "Origin": "https://skylinestart.evo-games.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }
        
        # 쿠키 헤더는 URL에서 추출
        try:
            from urllib.parse import urlparse, parse_qs
            parsed_url = urlparse(self.room_ws_url)
            query_params = parse_qs(parsed_url.query)
            if 'EVOSESSIONID' in query_params:
                headers["Cookie"] = f"EVOSESSIONID={query_params['EVOSESSIONID'][0]}"
        except Exception as e:
            logger.warning(f"URL에서 쿠키 추출 실패: {e}")
        
        try:
            # websockets 버전 호환성 문제 해결
            try:
                # 방법 1: connect 함수에 헤더 전달 (최신 버전)
                self.websocket = await websockets.connect(
                    self.room_ws_url, 
                    extra_headers=headers
                )
            except TypeError:
                # 방법 2: connect 함수에 헤더 전달하지 않음 (이전 버전)
                logger.info("이전 버전의 websockets 사용 - 헤더 설정 없이 연결 시도")
                self.websocket = await websockets.connect(self.room_ws_url)
            
            self.is_connected = True
            logger.info("방 WebSocket 연결 완료 ✅")
            
            # 메시지 수신 작업 시작
            self.task = asyncio.create_task(self._receive_messages())
            
            return True
        except Exception as e:
            logger.error(f"방 연결 오류: {e}")
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
            logger.info("방 WebSocket 연결 종료")
            return True
        except Exception as e:
            logger.error(f"방 연결 종료 오류: {e}")
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
                        logger.warning(f"Received invalid JSON from room")
                        
                except asyncio.TimeoutError:
                    # 30초 동안 메시지 없음 - 연결 확인 메시지 전송
                    logger.debug("No room messages received for 30 seconds, sending ping...")
                    try:
                        pong_waiter = await self.websocket.ping()
                        await asyncio.wait_for(pong_waiter, timeout=10.0)
                        logger.debug("Pong received, room connection is still active")
                    except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                        logger.warning("Room ping failed, connection seems to be lost")
                        # 연결이 끊어졌으므로 재연결 시도
                        self.is_connected = False
                        break
                    
        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"Room connection closed by server: {e}")
            self.is_connected = False
            # 정상적인 종료가 아닌 경우 재연결 시도
            if e.code != 1000:  # 1000은 정상 종료
                await self._attempt_reconnect()
            
        except asyncio.CancelledError:
            logger.info("Room message receiving task cancelled")
            raise
            
        except Exception as e:
            logger.error(f"Error in room message receiving: {e}")
            self.is_connected = False
            await self._attempt_reconnect()
    
    async def _attempt_reconnect(self):
        """웹소켓 재연결 시도"""
        # 이미 최대 재시도 횟수를 초과한 경우
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Room: 최대 재연결 시도 횟수({self.max_reconnect_attempts}회)를 초과했습니다. 재연결을 중단합니다.")
            return False
        
        # 마지막 재연결 시도 후 60초 이상 지났으면 재시도 횟수 초기화
        now = datetime.now()
        if (now - self.last_reconnect_attempt) > timedelta(seconds=60):
            self.reconnect_attempts = 0
        
        self.reconnect_attempts += 1
        self.last_reconnect_attempt = now
        
        # 백오프 지연 시간 계산 (1초, 2초, 4초...)
        delay = 2 ** (self.reconnect_attempts - 1)
        logger.info(f"Room: 재연결 시도 {self.reconnect_attempts}/{self.max_reconnect_attempts}... {delay}초 후 시도합니다.")
        
        await asyncio.sleep(delay)
        return await self.connect()
    
    async def _process_message(self, data: Dict[str, Any]):
        """수신된 메시지 처리"""
        # 외부 콜백 호출 (있는 경우)
        if self.on_message_callback:
            await self.on_message_callback(data)
        
        # 특정 메시지 타입 처리 예시 (방 특화 처리)
        msg_type = data.get("type", "unknown")
        if msg_type == "round.end":
            logger.info(f"🎲 게임 라운드 종료: {data.get('args', {})}")
        elif msg_type == "round.start":
            logger.info(f"🎲 게임 라운드 시작: {data.get('args', {})}")
        elif msg_type == "round.betting.opened":
            logger.info(f"💰 베팅 오픈: {data.get('args', {})}")
        elif msg_type == "round.betting.closed":
            logger.info(f"🔒 베팅 마감: {data.get('args', {})}")


class BettingSignal:
    """베팅 신호 데이터 클래스"""
    
    def __init__(self, room_id: str, position: str, amount: int, 
                 strategy: str, confidence: float, predicted_by: str):
        self.room_id = room_id
        self.position = position  # "player" or "banker"
        self.amount = amount
        self.strategy = strategy
        self.confidence = confidence
        self.predicted_by = predicted_by  # 예측 알고리즘
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "room_id": self.room_id,
            "position": self.position,
            "amount": self.amount,
            "strategy": self.strategy,
            "confidence": self.confidence,
            "predicted_by": self.predicted_by,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BettingSignal':
        signal = cls(
            room_id=data["room_id"],
            position=data["position"],
            amount=data["amount"],
            strategy=data["strategy"],
            confidence=data["confidence"],
            predicted_by=data["predicted_by"]
        )
        signal.timestamp = datetime.fromisoformat(data["timestamp"])
        return signal


class BettingExecutor:
    """베팅 신호 관리 및 방 모니터링 매니저"""
    
    def __init__(self):
        self.betting_sessions: Dict[str, Dict[str, Dict[str, Any]]] = {}  # user_id -> room_id -> session_data
        self.betting_configs: Dict[str, Dict[str, Dict[str, Any]]] = {}  # user_id -> room_id -> config
        self.connected_websockets: Dict[str, Dict[str, Set[WebSocket]]] = {}  # user_id -> room_id -> set of websockets
        self.betting_signals: Dict[str, Dict[str, List[BettingSignal]]] = {}  # user_id -> room_id -> signals
    
    def get_active_bettings_count(self) -> int:
        """활성 베팅 세션 수 반환"""
        count = 0
        for user_sessions in self.betting_sessions.values():
            for session in user_sessions.values():
                if session.get('task') is not None:
                    count += 1
        return count
    
    def has_betting_config(self, user_id: str, room_id: str) -> bool:
        """베팅 설정 존재 여부 확인"""
        return user_id in self.betting_configs and room_id in self.betting_configs[user_id]
    
    def has_betting_data(self, user_id: str, room_id: str) -> bool:
        """베팅 데이터 존재 여부 확인"""
        return user_id in self.betting_sessions and room_id in self.betting_sessions[user_id]
    
    def is_betting_running(self, user_id: str, room_id: str) -> bool:
        """베팅 모니터링 실행 여부 확인"""
        return (user_id in self.betting_sessions and 
                room_id in self.betting_sessions[user_id] and 
                self.betting_sessions[user_id][room_id].get('task') is not None)
    
    def set_betting_config(self, user_id: str, room_id: str, config: Dict[str, Any]):
        """베팅 설정 저장"""
        if user_id not in self.betting_configs:
            self.betting_configs[user_id] = {}
        
        self.betting_configs[user_id][room_id] = config
    
    def generate_betting_signal(self, user_id: str, room_id: str, 
                               position: str, strategy: str, 
                               confidence: float, predicted_by: str) -> BettingSignal:
        """베팅 신호 생성"""
        if user_id not in self.betting_configs or room_id not in self.betting_configs[user_id]:
            logger.warning(f"베팅 설정이 없습니다: 사용자 {user_id}, 방 {room_id}")
            return None
        
        config = self.betting_configs[user_id][room_id]
        amount = config.get('amount', 1000)
        
        signal = BettingSignal(
            room_id=room_id,
            position=position,
            amount=amount,
            strategy=strategy,
            confidence=confidence,
            predicted_by=predicted_by
        )
        
        # 신호 저장
        if user_id not in self.betting_signals:
            self.betting_signals[user_id] = {}
        
        if room_id not in self.betting_signals[user_id]:
            self.betting_signals[user_id][room_id] = []
        
        self.betting_signals[user_id][room_id].append(signal)
        
        return signal
    
    def get_betting_data(self, user_id: str, room_id: str) -> Dict[str, Any]:
        """베팅 데이터 반환"""
        if not self.has_betting_data(user_id, room_id):
            return {
                "status": "not_running",
                "betting_signals": [],
                "total_signals": 0
            }
        
        session_data = self.betting_sessions[user_id][room_id]
        signals = self.betting_signals.get(user_id, {}).get(room_id, [])
        
        return {
            "status": "running" if session_data.get('task') is not None else "stopped",
            "betting_signals": [signal.to_dict() for signal in signals[-10:]],  # 최근 10개만
            "total_signals": len(signals),
            "last_update": session_data.get('last_update', datetime.now().isoformat())
        }
    
    async def register_websocket(self, user_id: str, room_id: str, websocket: WebSocket):
        """웹소켓 연결 등록"""
        if user_id not in self.connected_websockets:
            self.connected_websockets[user_id] = {}
        
        if room_id not in self.connected_websockets[user_id]:
            self.connected_websockets[user_id][room_id] = set()
        
        await websocket.accept()
        self.connected_websockets[user_id][room_id].add(websocket)
        
        # 연결 즉시 현재 데이터 전송
        await self.send_init_data(user_id, room_id, websocket)
    
    def unregister_websocket(self, user_id: str, room_id: str, websocket: WebSocket):
        """웹소켓 연결 해제"""
        if (user_id in self.connected_websockets and 
            room_id in self.connected_websockets[user_id]):
            self.connected_websockets[user_id][room_id].discard(websocket)
    
    async def send_init_data(self, user_id: str, room_id: str, websocket: WebSocket):
        """초기 데이터 전송"""
        if self.has_betting_data(user_id, room_id):
            betting_data = self.get_betting_data(user_id, room_id)
            
            try:
                await websocket.send_json({
                    "type": "init_data",
                    "is_running": self.is_betting_running(user_id, room_id),
                    "betting_data": betting_data
                })
            except Exception as e:
                logger.error(f"베팅 초기 데이터 전송 오류: {e}")
    
    async def broadcast_to_room(self, user_id: str, room_id: str, message: dict):
        """특정 방의 모든 웹소켓 연결에 메시지 전송"""
        if (user_id not in self.connected_websockets or 
            room_id not in self.connected_websockets[user_id]):
            return
        
        dead_sockets = set()
        for websocket in self.connected_websockets[user_id][room_id]:
            try:
                await websocket.send_json(message)
            except Exception:
                dead_sockets.add(websocket)
        
        # 끊어진 소켓 제거
        for dead_socket in dead_sockets:
            self.connected_websockets[user_id][room_id].discard(dead_socket)
    
    async def start_monitoring(self, user_id: str, room_id: str, room_data: List[Dict[str, Any]], 
                              prediction_config: Dict[str, Any]) -> bool:
        """특정 방 모니터링 시작"""
        if not self.has_betting_config(user_id, room_id):
            logger.error(f"사용자 {user_id}의 방 {room_id} 베팅 설정이 없습니다.")
            return False
        
        if self.is_betting_running(user_id, room_id):
            logger.info(f"사용자 {user_id}의 방 {room_id} 베팅 모니터링이 이미 실행 중입니다.")
            return True
        
        config = self.betting_configs[user_id][room_id]
        
        # 사용자별 방별 데이터 저장소 초기화
        if user_id not in self.betting_sessions:
            self.betting_sessions[user_id] = {}
        
        if room_id not in self.betting_sessions[user_id]:
            self.betting_sessions[user_id][room_id] = {
                'client': None,
                'task': None,
                'last_update': datetime.now().isoformat()
            }
        
        # 기존 태스크 종료
        if self.betting_sessions[user_id][room_id].get('task') is not None:
            self.betting_sessions[user_id][room_id]['task'].cancel()
            try:
                await self.betting_sessions[user_id][room_id]['task']
            except asyncio.CancelledError:
                pass
        
        # 클라이언트 연결 종료
        if self.betting_sessions[user_id][room_id].get('client') is not None:
            await self.betting_sessions[user_id][room_id]['client'].disconnect()
        
        # 방 웹소켓 URL 확인
        room_ws_url = config.get('room_websocket_url')
        if not room_ws_url:
            logger.error(f"방 {room_id}의 WebSocket URL이 설정되지 않았습니다.")
            # 실제 구현에서는 로비 URL에서 방 URL 생성 로직 추가 필요
            return False
        
        # 메시지 처리 콜백 함수
        async def on_message_callback(data: Dict[str, Any]):
            msg_type = data.get("type", "unknown")
            
            # 베팅 관련 메시지 처리
            if msg_type == "round.betting.opened":
                # 베팅 오픈 시 베팅 전략에 따라 신호 생성
                await self._generate_bet_signal(user_id, room_id, data, prediction_config)
            
            elif msg_type == "round.end":
                # 라운드 종료 시 결과 처리
                await self._process_round_result(user_id, room_id, data)
            
            # 베팅 데이터 업데이트 및 브로드캐스트
            betting_data = self.get_betting_data(user_id, room_id)
            await self.broadcast_to_room(user_id, room_id, {
                "type": "betting_update",
                "betting_data": betting_data
            })
        
        # 방 클라이언트 생성
        client = RoomWebSocketClient(
            room_ws_url=room_ws_url,
            on_message_callback=on_message_callback
        )
        
        # 클라이언트 연결
        connected = await client.connect()
        if not connected:
            logger.error(f"사용자 {user_id}의 방 {room_id} 연결 실패")
            return False
        
        # 베팅 모니터링 태스크
        async def run_monitoring():
            try:
                logger.info(f"사용자 {user_id}의 방 {room_id} 베팅 모니터링 시작")
                
                # 베팅 상태 업데이트 전송
                await self.broadcast_to_room(user_id, room_id, {
                    "type": "status_update",
                    "is_running": True
                })
                
                # 클라이언트 연결 유지
                rounds_monitored = 0
                max_rounds = config.get('max_rounds', 10)
                
                while client.is_connected and rounds_monitored < max_rounds:
                    await asyncio.sleep(1)
                    
                    # 최대 라운드 도달 시 종료
                    if rounds_monitored >= max_rounds:
                        logger.info(f"최대 라운드 수({max_rounds})에 도달하여 모니터링 종료")
                        break
                
            except asyncio.CancelledError:
                logger.info(f"사용자 {user_id}의 방 {room_id} 베팅 모니터링 작업이 취소되었습니다.")
                raise
            except Exception as e:
                logger.error(f"사용자 {user_id}의 방 {room_id} 베팅 모니터링 오류: {e}")
            finally:
                await client.disconnect()
                
                # 베팅 상태 업데이트 전송
                await self.broadcast_to_room(user_id, room_id, {
                    "type": "status_update",
                    "is_running": False
                })
                
                logger.info(f"사용자 {user_id}의 방 {room_id} 베팅 모니터링 종료")
                
                # 태스크 참조 제거
                if (user_id in self.betting_sessions and 
                    room_id in self.betting_sessions[user_id]):
                    self.betting_sessions[user_id][room_id]['task'] = None
        
        # 클라이언트 및 태스크 저장
        self.betting_sessions[user_id][room_id]['client'] = client
        self.betting_sessions[user_id][room_id]['task'] = asyncio.create_task(run_monitoring())
        
        return True
    
    async def stop_monitoring(self, user_id: str, room_id: str) -> bool:
        """베팅 모니터링 중지"""
        if not self.is_betting_running(user_id, room_id):
            logger.info(f"사용자 {user_id}의 방 {room_id} 베팅 모니터링이 실행 중이 아닙니다.")
            return False
        
        # 태스크 종료
        self.betting_sessions[user_id][room_id]['task'].cancel()
        try:
            await self.betting_sessions[user_id][room_id]['task']
        except asyncio.CancelledError:
            pass
        
        # 클라이언트 연결 종료
        if self.betting_sessions[user_id][room_id].get('client') is not None:
            await self.betting_sessions[user_id][room_id]['client'].disconnect()
        
        # 상태 업데이트
        self.betting_sessions[user_id][room_id]['task'] = None
        self.betting_sessions[user_id][room_id]['client'] = None
        
        return True
    
    async def _generate_bet_signal(self, user_id: str, room_id: str, data: Dict[str, Any], 
                                 prediction_config: Dict[str, Any]):
        """베팅 신호 생성"""
        if not self.is_betting_running(user_id, room_id):
            return
        
        config = self.betting_configs[user_id][room_id]
        strategy = config.get('strategy', 'follow_streak')
        
        # 이 부분에서 예측 알고리즘을 통해 베팅 신호 생성
        # 실제 구현에서는 prediction_engine 모듈과 연동하여 예측 수행
        
        # 베팅 위치 임시 결정 (실제로는 예측 알고리즘 사용)
        position = "player"  # 또는 "banker"
        confidence = 0.8
        predicted_by = "pattern_analysis"
        
        # 베팅 신호 생성
        signal = self.generate_betting_signal(
            user_id=user_id,
            room_id=room_id,
            position=position,
            strategy=strategy,
            confidence=confidence,
            predicted_by=predicted_by
        )
        
        if signal:
            logger.info(f"💰 베팅 신호 생성: 사용자 {user_id}, 방 {room_id}, 위치 {position}, 신뢰도 {confidence}")
            
            # 베팅 신호 브로드캐스트
            await self.broadcast_to_room(user_id, room_id, {
                "type": "bet_signal",
                "signal": signal.to_dict()
            })
        
        # 세션 데이터 업데이트
        self.betting_sessions[user_id][room_id]['last_update'] = datetime.now().isoformat()
    
    async def _process_round_result(self, user_id: str, room_id: str, data: Dict[str, Any]):
        """라운드 결과 처리"""
        if not self.is_betting_running(user_id, room_id):
            return
        
        # 라운드 결과 확인
        result = data.get('args', {}).get('result', {})
        winner = result.get('winner', '')
        
        # 결과 로깅
        logger.info(f"🎲 게임 결과: 사용자 {user_id}, 방 {room_id}, 승자 {winner}")
        
        # 세션 데이터 업데이트
        self.betting_sessions[user_id][room_id]['last_update'] = datetime.now().isoformat()