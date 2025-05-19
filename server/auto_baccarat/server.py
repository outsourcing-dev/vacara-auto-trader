import os
import sys
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# 상위 디렉토리 모듈 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 공통 모듈 임포트
from common.config import Config
from monitor.lobby_monitor import LobbyMonitor, ClientConfig
from betting.bet_executor import BettingExecutor
from prediction.prediction_engine import PredictionEngine

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("baccarat_server")

# FastAPI 앱 생성
app = FastAPI(title="Vacara Auto Baccarat API Server")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 배포 시 더 제한적으로 설정
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 글로벌 매니저 인스턴스
lobby_manager = LobbyMonitor()
betting_manager = BettingExecutor()
prediction_engine = PredictionEngine()

# 요청 모델들
class SessionConfig(BaseModel):
    session_id: str
    bare_session_id: str
    instance: str
    client_version: str
    user_id: str

class BettingConfig(BaseModel):
    room_id: str
    room_websocket_url: Optional[str] = None
    user_id: str
    amount: int = 1000
    max_rounds: int = 10
    strategy: str = "follow_streak"  # 베팅 전략

class PredictionSettings(BaseModel):
    algorithm: str = "pattern_recognition"  # 예측 알고리즘
    sample_size: int = 15  # 패턴 분석에 사용할 샘플 크기
    user_id: str

class StreakSettings(BaseModel):
    player_streak: int = 3
    banker_streak: int = 3
    min_results: int = 10
    user_id: str

# API 엔드포인트: 상태 확인
@app.get("/api/status")
async def get_status():
    return {
        "status": "running",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "active_monitors": lobby_manager.get_active_monitors_count(),
        "active_bettings": betting_manager.get_active_bettings_count()
    }

# WebSocket 연결 엔드포인트: 로비 모니터링
@app.websocket("/ws/baccarat/{user_id}")
async def baccarat_websocket(websocket: WebSocket, user_id: str):
    await lobby_manager.register_websocket(user_id, websocket)
    
    try:
        while True:
            # 클라이언트가 보내는 메시지 대기 (핑/퐁 등)
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        lobby_manager.unregister_websocket(user_id, websocket)

# WebSocket 연결 엔드포인트: 베팅 모니터링
@app.websocket("/ws/betting/{user_id}/{room_id}")
async def betting_websocket(websocket: WebSocket, user_id: str, room_id: str):
    await betting_manager.register_websocket(user_id, room_id, websocket)
    
    try:
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        betting_manager.unregister_websocket(user_id, room_id, websocket)

#############################
# 로비 모니터링 엔드포인트 #
#############################

# API 엔드포인트: 세션 설정
@app.post("/api/baccarat/config")
async def set_baccarat_config(config: SessionConfig):
    client_config = ClientConfig(
        session_id=config.session_id,
        bare_session_id=config.bare_session_id,
        instance=config.instance,
        client_version=config.client_version
    )
    
    lobby_manager.set_session_config(config.user_id, client_config)
    
    return {"status": "success", "message": "세션 설정이 저장되었습니다."}

# API 엔드포인트: 연패 설정
@app.post("/api/baccarat/streak-settings")
async def set_streak_settings(settings: StreakSettings):
    lobby_manager.set_streak_settings(settings.user_id, {
        "player_streak": settings.player_streak,
        "banker_streak": settings.banker_streak,
        "min_results": settings.min_results
    })
    
    # 설정 변경 즉시 연패 데이터 재계산 및 전송
    await lobby_manager.recalculate_streaks(settings.user_id)
    
    return {"status": "success", "message": "연패 설정이 저장되었습니다."}

# API 엔드포인트: 예측 알고리즘 설정
@app.post("/api/baccarat/prediction-settings")
async def set_prediction_settings(settings: PredictionSettings):
    prediction_engine.set_algorithm_settings(settings.user_id, {
        "algorithm": settings.algorithm,
        "sample_size": settings.sample_size
    })
    
    # 설정 변경 즉시 예측 데이터 재계산 및 전송
    await lobby_manager.recalculate_predictions(settings.user_id)
    
    return {"status": "success", "message": "예측 알고리즘 설정이 저장되었습니다."}

# API 엔드포인트: 로비 모니터링 시작
@app.post("/api/baccarat/start/{user_id}")
async def start_baccarat_monitor(user_id: str):
    if not lobby_manager.has_session_config(user_id):
        return {"status": "error", "message": "세션 설정이 필요합니다."}
    
    success = await lobby_manager.start_client(user_id, prediction_engine)
    
    if success:
        return {"status": "success", "message": "바카라 로비 모니터링이 시작되었습니다."}
    else:
        return {"status": "error", "message": "바카라 로비 모니터링 시작 실패. 세션 설정을 확인하세요."}

# API 엔드포인트: 로비 모니터링 중지
@app.post("/api/baccarat/stop/{user_id}")
async def stop_baccarat_monitor(user_id: str):
    success = await lobby_manager.stop_client(user_id)
    
    if success:
        return {"status": "success", "message": "바카라 로비 모니터링이 중지되었습니다."}
    else:
        return {"status": "error", "message": "바카라 로비 모니터링이 실행 중이 아닙니다."}

# API 엔드포인트: 바카라 데이터 조회
@app.get("/api/baccarat/data/{user_id}")
async def get_baccarat_data(user_id: str):
    if not lobby_manager.has_user_data(user_id):
        return {"status": "error", "message": "사용자 데이터가 없습니다."}
    
    monitor_data = lobby_manager.get_monitor_data(user_id)
    
    return {
        "status": "success",
        "is_running": lobby_manager.is_client_running(user_id),
        "monitor_data": monitor_data
    }

# API 엔드포인트: 방 매핑 및 필터링 설정
@app.post("/api/baccarat/room-mappings/{user_id}")
async def set_room_mappings(user_id: str, request: Request):
    mappings = await request.json()
    
    if not isinstance(mappings, dict):
        raise HTTPException(status_code=400, detail="유효하지 않은 방 매핑 형식입니다.")
    
    lobby_manager.set_room_mappings(user_id, mappings)
    
    return {"status": "success", "message": "방 매핑이 저장되었습니다."}

#############################
# 베팅 실행 엔드포인트 #
#############################

# API 엔드포인트: 베팅 설정
@app.post("/api/baccarat/betting-config")
async def set_betting_config(config: BettingConfig):
    betting_manager.set_betting_config(config.user_id, config.room_id, {
        "amount": config.amount,
        "max_rounds": config.max_rounds,
        "strategy": config.strategy,
        "room_websocket_url": config.room_websocket_url
    })
    
    return {"status": "success", "message": "베팅 설정이 저장되었습니다."}

# API 엔드포인트: 베팅 시작
@app.post("/api/baccarat/betting/start/{user_id}/{room_id}")
async def start_betting(user_id: str, room_id: str):
    if not betting_manager.has_betting_config(user_id, room_id):
        return {"status": "error", "message": "베팅 설정이 필요합니다."}
    
    # 로비 모니터 데이터 가져오기
    room_data = lobby_manager.get_room_data(user_id, room_id)
    if not room_data:
        return {"status": "error", "message": "해당 방에 대한 데이터가 없습니다."}
    
    # 예측 엔진 설정
    prediction_config = prediction_engine.get_algorithm_settings(user_id)
    
    # 베팅 시작
    success = await betting_manager.start_betting(user_id, room_id, room_data, prediction_config)
    
    if success:
        return {"status": "success", "message": f"{room_id} 방에서 베팅이 시작되었습니다."}
    else:
        return {"status": "error", "message": "베팅 시작 실패. 설정을 확인하세요."}

# API 엔드포인트: 베팅 중지
@app.post("/api/baccarat/betting/stop/{user_id}/{room_id}")
async def stop_betting(user_id: str, room_id: str):
    success = await betting_manager.stop_betting(user_id, room_id)
    
    if success:
        return {"status": "success", "message": f"{room_id} 방에서 베팅이 중지되었습니다."}
    else:
        return {"status": "error", "message": "베팅이 실행 중이 아닙니다."}

# API 엔드포인트: 베팅 데이터 조회
@app.get("/api/baccarat/betting/data/{user_id}/{room_id}")
async def get_betting_data(user_id: str, room_id: str):
    if not betting_manager.has_betting_data(user_id, room_id):
        return {"status": "error", "message": "베팅 데이터가 없습니다."}
    
    betting_data = betting_manager.get_betting_data(user_id, room_id)
    
    return {
        "status": "success",
        "is_running": betting_manager.is_betting_running(user_id, room_id),
        "betting_data": betting_data
    }

# 웹소켓 URL에서 설정 추출 유틸리티
@app.post("/api/utils/extract-config")
async def extract_config_from_url(request: Request):
    data = await request.json()
    ws_url = data.get("websocket_url")
    
    if not ws_url:
        return {"status": "error", "message": "WebSocket URL이 제공되지 않았습니다."}
    
    try:
        from urllib.parse import urlparse, parse_qs
        
        # URL 파싱
        parsed_url = urlparse(ws_url)
        query_params = parse_qs(parsed_url.query)
        
        # 필요한 정보 추출
        bare_session_id = parsed_url.path.split('/')[-1]
        session_id = query_params.get('EVOSESSIONID', [''])[0]
        instance_param = query_params.get('instance', [''])[0]
        instance = instance_param.split('-')[0] if instance_param else ''
        client_version = query_params.get('client_version', [''])[0]
        
        # 값이 유효한지 확인
        if not all([bare_session_id, session_id, instance, client_version]):
            return {"status": "error", "message": "유효하지 않은 WebSocket URL입니다."}
        
        return {
            "status": "success",
            "config": {
                "session_id": session_id,
                "bare_session_id": bare_session_id,
                "instance": instance,
                "client_version": client_version
            }
        }
    except Exception as e:
        logger.error(f"URL 파싱 오류: {e}")
        return {"status": "error", "message": f"URL 파싱 오류: {e}"}

@app.get("/api/baccarat/room-data/{user_id}/{room_id}")
async def get_room_raw_data(user_id: str, room_id: str):
    """특정 방의 상세 데이터 조회 (디버깅용)"""
    if not lobby_manager.has_user_data(user_id):
        return {"status": "error", "message": "사용자 데이터가 없습니다."}
    
    room_data = lobby_manager.get_room_data(user_id, room_id)
    
    if not room_data:
        return {"status": "error", "message": "해당 방의 데이터가 없습니다."}
        
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
        
        # 전체 결과 정렬 시도
        sorted_results = sorted(room_data, key=get_sort_key)
        
        # 최근 15개 결과 추출
        recent_results = sorted_results[-15:] if len(sorted_results) >= 15 else sorted_results
        
        # 결과를 읽기 쉬운 형태로 변환
        readable_results = []
        for result in recent_results:
            c = result.get('c', '')
            winner = "Player" if c == 'B' else ("Banker" if c == 'R' else "Tie/Other")
            
            extras = []
            if result.get('nat') == 1:
                extras.append('Natural')
            if result.get('ties') == 1:
                extras.append('Tie')
            if result.get('pp') == 1:
                extras.append('Player Pair')
            if result.get('bp') == 1:
                extras.append('Banker Pair')
                
            readable_results.append({
                "position": result.get("pos", []),
                "winner": winner,
                "extras": extras,
                "raw_code": c
            })
            
        # 결과 패턴 문자열 (과거 -> 최근 순)
        result_pattern = "".join([
            "P" if r.get('c', '') == 'B' else ("B" if r.get('c', '') == 'R' else "T") 
            for r in sorted_results[-15:]
        ])
        
        # 결과 통계
        total_games = len(sorted_results)
        recent_count = len(recent_results)
        
        player_wins = sum(1 for r in recent_results if r.get('c', '') == 'B')
        banker_wins = sum(1 for r in recent_results if r.get('c', '') == 'R')
        ties = recent_count - player_wins - banker_wins
        
        return {
            "status": "success", 
            "room_id": room_id, 
            "room_name": lobby_manager.get_room_mappings(user_id).get(room_id, room_id),
            "total_games": total_games,
            "recent_count": recent_count,
            "result_pattern": result_pattern,
            "stats": {
                "player_wins": player_wins,
                "banker_wins": banker_wins,
                "ties": ties,
                "player_rate": round(player_wins / recent_count * 100, 1) if recent_count > 0 else 0,
                "banker_rate": round(banker_wins / recent_count * 100, 1) if recent_count > 0 else 0
            },
            "readable_results": readable_results,
            "raw_data_sample": sorted_results[:3] if sorted_results else []  # 원시 데이터 일부 포함
        }
    except Exception as e:
        logger.error(f"방 데이터 처리 중 오류 발생: {e}")
        import traceback
        error_trace = traceback.format_exc()
        
        return {
            "status": "error", 
            "message": f"데이터 처리 오류: {str(e)}", 
            "room_id": room_id,
            "data_count": len(room_data),
            "sample_data": room_data[:2] if room_data else [],
            "error_trace": error_trace
        }
        
if __name__ == "__main__":
    # 서버 실행
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=False)