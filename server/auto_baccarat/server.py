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

# 공통 모듈 임포트 (리팩토링된 버전)
from common.config import Config
from monitor.lobby_monitor import LobbyMonitor, ClientConfig

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("baccarat_server")

# FastAPI 앱 생성
app = FastAPI(title="Vacara Auto Baccarat API Server (Simple Version)")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 글로벌 매니저 인스턴스 (간소화)
lobby_manager = LobbyMonitor()

# 요청 모델들 (간소화)
class SessionConfig(BaseModel):
    session_id: str
    bare_session_id: str
    instance: str
    client_version: str
    user_id: str

# API 엔드포인트: 상태 확인
@app.get("/api/status")
async def get_status():
    return {
        "status": "running",
        "version": "1.0.0-simple",
        "timestamp": datetime.now().isoformat(),
        "active_monitors": lobby_manager.get_active_monitors_count(),
        "description": "Simple room monitoring without prediction"
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

# API 엔드포인트: 로비 모니터링 시작
@app.post("/api/baccarat/start/{user_id}")
async def start_baccarat_monitor(user_id: str):
    if not lobby_manager.has_session_config(user_id):
        return {"status": "error", "message": "세션 설정이 필요합니다."}
    
    success = await lobby_manager.start_client(user_id)
    
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

# API 엔드포인트: 바카라 데이터 조회 (간소화)
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

# API 엔드포인트: 방 매핑 설정
@app.post("/api/baccarat/room-mappings/{user_id}")
async def set_room_mappings(user_id: str, request: Request):
    mappings = await request.json()
    
    if not isinstance(mappings, dict):
        raise HTTPException(status_code=400, detail="유효하지 않은 방 매핑 형식입니다.")
    
    lobby_manager.set_room_mappings(user_id, mappings)
    
    return {"status": "success", "message": "방 매핑이 저장되었습니다."}

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
    """특정 방의 상세 데이터 조회"""
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
        
        # 결과를 읽기 쉬운 형태로 변환
        readable_results = []
        result_pattern = []
        
        for result in sorted_results:
            c = result.get('c', '')
            if c == 'B':  # Player 승리
                winner = "Player"
                pattern_char = "P"
            elif c == 'R':  # Banker 승리
                winner = "Banker"
                pattern_char = "B"
            else:  # Tie 또는 기타
                winner = "Tie/Other"
                pattern_char = "T"
            
            result_pattern.append(pattern_char)
            
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
        
        # 결과 통계
        total_games = len(sorted_results)
        player_wins = result_pattern.count('P')
        banker_wins = result_pattern.count('B')
        ties = result_pattern.count('T')
        
        return {
            "status": "success", 
            "room_id": room_id, 
            "room_name": lobby_manager.get_room_mappings(user_id).get(room_id, room_id),
            "total_games": total_games,
            "result_pattern": "".join(result_pattern),
            "recent_20": "".join(result_pattern[-20:]) if len(result_pattern) >= 20 else "".join(result_pattern),
            "stats": {
                "player_wins": player_wins,
                "banker_wins": banker_wins,
                "ties": ties,
                "player_rate": round(player_wins / total_games * 100, 1) if total_games > 0 else 0,
                "banker_rate": round(banker_wins / total_games * 100, 1) if total_games > 0 else 0,
                "tie_rate": round(ties / total_games * 100, 1) if total_games > 0 else 0
            },
            "readable_results": readable_results[-10:] if len(readable_results) >= 10 else readable_results,  # 최근 10개만
            "raw_data_sample": sorted_results[:3] if sorted_results else []
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

# API 엔드포인트: 방 요약 정보 출력
@app.get("/api/baccarat/summary/{user_id}")
async def get_rooms_summary(user_id: str):
    """모든 필터링된 방의 요약 정보 조회"""
    if not lobby_manager.has_user_data(user_id):
        return {"status": "error", "message": "사용자 데이터가 없습니다."}
    
    monitor_data = lobby_manager.get_monitor_data(user_id)
    filtered_rooms = monitor_data.get("filtered_rooms", [])
    
    if not filtered_rooms:
        return {
            "status": "success",
            "message": "필터링된 방이 없습니다.",
            "total_rooms": 0,
            "rooms": []
        }
    
    return {
        "status": "success",
        "total_rooms": len(filtered_rooms),
        "rooms": filtered_rooms,
        "updated_at": monitor_data.get("updated_at"),
        "pattern_legend": {
            "P": "Player 승리",
            "B": "Banker 승리", 
            "T": "Tie"
        }
    }

if __name__ == "__main__":
    # 서버 실행
    print("🎰 Vacara Auto Baccarat Server (Simple Version) 시작")
    print("📊 기능: 필터링된 방 모니터링 (예측픽 제거)")
    print("🔗 API 문서: http://localhost:8080/docs")
    print("=" * 50)
    
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=False)