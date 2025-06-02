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
from prediction.streak_analyzer import StreakAnalyzer

# 상위 디렉토리 모듈 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
streak_analyzer = StreakAnalyzer()

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

# server.py에 추가할 코드

# 기존 import에 추가
from prediction.streak_analyzer import StreakAnalyzer

# 기존 글로벌 매니저 인스턴스에 추가
streak_analyzer = StreakAnalyzer()

# 요청 모델 추가
class StreakPredictionRequest(BaseModel):
    streak_count: int = 3  # 연패 기준 (기본값 3)
    user_id: str

#############################
# 연패 예측 분석 엔드포인트 #
#############################

@app.post("/api/baccarat/find-streak-rooms")
async def find_streak_rooms(request: StreakPredictionRequest):
    """
    연패 조건에 맞는 방 찾기
    
    Args:
        request: 연패 기준과 사용자 ID
        
    Returns:
        연패 조건 만족하는 방 목록과 분석 통계
    """
    user_id = request.user_id
    streak_count = request.streak_count
    
    # 사용자 데이터 확인
    if not lobby_manager.has_user_data(user_id):
        raise HTTPException(
            status_code=400, 
            detail=f"사용자 {user_id}의 데이터가 없습니다. 먼저 로비 모니터링을 시작하세요."
        )
    
    # 사용자의 방 데이터 가져오기
    if user_id not in lobby_manager.clients or 'room_data' not in lobby_manager.clients[user_id]:
        raise HTTPException(
            status_code=400,
            detail="방 데이터가 없습니다. 로비 모니터링이 실행 중인지 확인하세요."
        )
    
    room_data = lobby_manager.clients[user_id]['room_data']
    room_mappings = lobby_manager.get_room_mappings(user_id)
    
    # 연패 방 분석 시작
    logger.info(f"사용자 {user_id}의 {streak_count}연패 방 분석 시작")
    
    try:
        # 분석 통계 먼저 계산
        statistics = streak_analyzer.get_analysis_statistics(room_data, streak_count)
        
        # 연패 방 찾기
        streak_rooms = streak_analyzer.find_streak_rooms(
            room_data, room_mappings, streak_count
        )
        
        # 분석 결과 요약 로그
        summary = streak_analyzer.format_analysis_summary(streak_rooms, statistics)
        logger.info(f"\n{summary}")
        
        # 응답 데이터 구성
        response_data = {
            "status": "success",
            "streak_count": streak_count,
            "analysis_statistics": statistics,
            "streak_rooms": streak_rooms,
            "total_found": len(streak_rooms),
            "analysis_summary": summary
        }
        
        return response_data
        
    except Exception as e:
        logger.error(f"연패 방 분석 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        raise HTTPException(
            status_code=500,
            detail=f"연패 방 분석 중 오류가 발생했습니다: {str(e)}"
        )

@app.get("/api/baccarat/streak-analysis-stats/{user_id}")
async def get_streak_analysis_stats(user_id: str, streak_count: int = 3):
    """
    연패 분석 통계만 조회 (실제 분석 없이 통계 정보만)
    """
    if not lobby_manager.has_user_data(user_id):
        raise HTTPException(
            status_code=400,
            detail=f"사용자 {user_id}의 데이터가 없습니다."
        )
    
    room_data = lobby_manager.clients[user_id].get('room_data', {})
    
    if not room_data:
        raise HTTPException(
            status_code=400,
            detail="방 데이터가 없습니다."
        )
    
    try:
        statistics = streak_analyzer.get_analysis_statistics(room_data, streak_count)
        
        return {
            "status": "success",
            "statistics": statistics,
            "message": f"총 {statistics['total_rooms']}개 방 중 {statistics['sufficient_data_rooms']}개 방이 분석 가능합니다."
        }
        
    except Exception as e:
        logger.error(f"연패 분석 통계 조회 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"통계 조회 중 오류가 발생했습니다: {str(e)}"
        )

@app.get("/api/baccarat/room-prediction-test/{user_id}/{room_id}")
async def test_room_prediction(user_id: str, room_id: str, streak_count: int = 3):
    """
    특정 방의 연패 예측 테스트 (디버깅용)
    """
    if not lobby_manager.has_user_data(user_id):
        raise HTTPException(status_code=400, detail="사용자 데이터가 없습니다.")
    
    room_data = lobby_manager.clients[user_id].get('room_data', {})
    room_mappings = lobby_manager.get_room_mappings(user_id)
    
    if room_id not in room_data:
        raise HTTPException(status_code=404, detail=f"방 {room_id}의 데이터가 없습니다.")
    
    try:
        raw_results = room_data[room_id]
        room_name = room_mappings.get(room_id, room_id)
        
        # 결과 필터링
        filtered_results = streak_analyzer._filter_results(raw_results)
        
        # 연패 예측 검증
        validation_result = streak_analyzer.validator.validate_streak_predictions(
            filtered_results, streak_count
        )
        
        # 상세 로그 생성
        detailed_log = streak_analyzer.validator.format_prediction_log(
            room_id, room_name, filtered_results, validation_result
        )
        
        return {
            "status": "success",
            "room_id": room_id,
            "room_name": room_name,
            "total_games": len(filtered_results),
            "filtered_results": ''.join(filtered_results),
            "validation_result": validation_result,
            "detailed_log": detailed_log,
            "is_streak_room": validation_result["is_streak"]
        }
        
    except Exception as e:
        logger.error(f"방 예측 테스트 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"테스트 중 오류가 발생했습니다: {str(e)}"
        )
        
if __name__ == "__main__":
    # 서버 실행
    print("🎰 Vacara Auto Baccarat Server (Simple Version) 시작")
    print("📊 기능: 필터링된 방 모니터링 (예측픽 제거)")
    print("🔗 API 문서: http://localhost:8080/docs")
    print("=" * 50)
    
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=False)