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

# 새로 추가된 모듈들
from storage.room_data_manager import RoomDataManager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("baccarat_server")

# FastAPI 앱 생성
app = FastAPI(title="Vacara Auto Baccarat API Server - Choice Pick Integration")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 글로벌 매니저 인스턴스
lobby_manager = LobbyMonitor()
room_data_manager = RoomDataManager()

# 요청 모델들 (실제 프론트엔드 데이터 형식에 맞춤)
class SessionConfig(BaseModel):
    session_id: str
    bare_session_id: str
    instance: str
    client_version: str
    user_id: str

class RoomResultsRequest(BaseModel):
    room_id: str
    mapped_room_name: str  # 실제 데이터에서는 mapped_room_name 사용
    all_results: List[str]  # 전체 결과 리스트 (R, B 형태)
    total_results: int
    latest_result: str
    timestamp: Optional[str] = None  # ISO 형식

class StreakRoomsRequest(BaseModel):
    min_streak: int = 3

# ==========================================
# 기본 API 엔드포인트
# ==========================================

@app.get("/api/status")
async def get_status():
    stats = room_data_manager.get_stats()
    return {
        "status": "running",
        "version": "2.0.0-choice-pick-integrated",
        "timestamp": datetime.now().isoformat(),
        "active_monitors": lobby_manager.get_active_monitors_count(),
        "room_stats": stats,
        "description": "Choice Pick based streak detection system"
    }

# ==========================================
# 프론트엔드 연동 API (초이스픽 기반)
# ==========================================

# server.py의 수정된 API 부분

@app.get("/api/rooms/streak/{room_id}")
async def get_room_streak_info(room_id: str):
    """
    특정 방의 현재 연패 수 조회
    """
    try:
        if room_id not in room_data_manager.room_raw_results:
            return {
                "status": "not_found",
                "message": "해당 방의 데이터를 찾을 수 없습니다.",
                "room_id": room_id
            }
        
        room_name = room_data_manager.get_room_name(room_id)
        raw_results = room_data_manager.room_raw_results[room_id]
        
        # 연패 계산
        streak_info = room_data_manager.streak_calculator.calculate_room_streak(
            room_id, room_name, raw_results
        )
        
        if streak_info:
            return {
                "status": "success",
                "room_name": streak_info["room_name"],
                "current_streak": streak_info["streak_count"]
            }
        else:
            return {
                "status": "insufficient_data",
                "message": "데이터 부족 (최소 16개 게임 필요)",
                "room_id": room_id
            }
    
    except Exception as e:
        logger.error(f"연패 정보 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"연패 정보 조회 중 오류 발생: {str(e)}")

@app.post("/api/rooms/find-streak")
async def find_streak_rooms(request: StreakRoomsRequest):
    """
    조건에 맞는 연패 방 목록 조회 - 단순화 버전
    """
    try:
        # 원시 결과 데이터를 올바른 형태로 변환
        rooms_data = {}
        for room_id, raw_results in room_data_manager.room_raw_results.items():
            rooms_data[room_id] = {"results": raw_results}
        
        # 연패 분석
        streak_rooms = room_data_manager.room_analyzer.analyze_rooms(
            rooms_data, 
            room_data_manager.filtered_rooms, 
            request.min_streak
        )
        
        return {
            "status": "success",
            "streak_rooms": streak_rooms,  # [{"room_name": "...", "current_streak": 5}, ...]
            "total_found": len(streak_rooms),
            "min_streak": request.min_streak
        }
    
    except Exception as e:
        logger.error(f"연패 방 검색 오류: {e}")
        raise HTTPException(status_code=500, detail=f"연패 방 검색 중 오류 발생: {str(e)}")

# 방 결과 수신 API도 단순화
@app.post("/api/rooms/results")
async def receive_room_results(request: RoomResultsRequest):
    """
    프론트엔드에서 방 결과 데이터 수신 - 단순화 버전
    """
    try:
        # R/B를 P/B로 변환
        converted_results = []
        for result in request.all_results:
            if result == "R":  # Banker 승리
                converted_results.append("B")
            elif result == "B":  # Player 승리  
                converted_results.append("P")
        
        success = room_data_manager.update_room_results(
            room_id=request.room_id,
            room_name=request.mapped_room_name,
            recent_results=converted_results,
            round_number=request.total_results
        )
        
        if success:
            # 즉시 현재 연패 수 계산
            room_name = room_data_manager.get_room_name(request.room_id)
            raw_results = room_data_manager.room_raw_results[request.room_id]
            
            streak_info = room_data_manager.streak_calculator.calculate_room_streak(
                request.room_id, room_name, raw_results
            )
            
            response_data = {
                "status": "success",
                "room_name": request.mapped_room_name,
                "total_results": request.total_results
            }
            
            # 연패 정보가 있으면 추가
            if streak_info:
                response_data["current_streak"] = streak_info["streak_count"]
                logger.info(f"🔥 {request.mapped_room_name}: {streak_info['streak_count']}연패")
            else:
                response_data["current_streak"] = 0
                logger.info(f"ℹ️ {request.mapped_room_name}: 데이터 부족 또는 연패 없음")
            
            return response_data
        else:
            return {
                "status": "filtered_out",
                "message": "필터링되지 않은 방입니다.",
                "room_id": request.room_id
            }
    
    except Exception as e:
        logger.error(f"방 결과 처리 오류: {e}")
        raise HTTPException(status_code=500, detail=f"방 결과 처리 중 오류 발생: {str(e)}")
    
@app.get("/api/rooms/status")
async def get_all_room_status():
    """
    모든 방 상태 정보 조회 (초이스픽 기반)
    """
    try:
        rooms_data = room_data_manager.get_all_room_status()
        
        return {
            "status": "success",
            "rooms_data": rooms_data
        }
    
    except Exception as e:
        logger.error(f"전체 방 상태 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"방 상태 조회 중 오류 발생: {str(e)}")

@app.get("/api/rooms/analysis/{room_id}")
async def get_room_analysis_details(room_id: str):
    """
    특정 방의 상세 초이스픽 분석 정보 조회
    """
    try:
        analysis_details = room_data_manager.get_room_analysis_details(room_id)
        
        if analysis_details:
            return {
                "status": "success",
                "analysis": analysis_details
            }
        else:
            return {
                "status": "not_found",
                "message": "해당 방의 데이터를 찾을 수 없습니다.",
                "room_id": room_id
            }
    
    except Exception as e:
        logger.error(f"방 분석 상세 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"방 분석 조회 중 오류 발생: {str(e)}")

# ==========================================
# 기존 로비 모니터링 API (유지)
# ==========================================

@app.websocket("/ws/baccarat/{user_id}")
async def baccarat_websocket(websocket: WebSocket, user_id: str):
    await lobby_manager.register_websocket(user_id, websocket)
    
    try:
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        lobby_manager.unregister_websocket(user_id, websocket)

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

@app.post("/api/baccarat/start/{user_id}")
async def start_baccarat_monitor(user_id: str):
    if not lobby_manager.has_session_config(user_id):
        return {"status": "error", "message": "세션 설정이 필요합니다."}
    
    success = await lobby_manager.start_client(user_id)
    
    if success:
        return {"status": "success", "message": "바카라 로비 모니터링이 시작되었습니다."}
    else:
        return {"status": "error", "message": "바카라 로비 모니터링 시작 실패. 세션 설정을 확인하세요."}

@app.post("/api/baccarat/stop/{user_id}")
async def stop_baccarat_monitor(user_id: str):
    success = await lobby_manager.stop_client(user_id)
    
    if success:
        return {"status": "success", "message": "바카라 로비 모니터링이 중지되었습니다."}
    else:
        return {"status": "error", "message": "바카라 로비 모니터링이 실행 중이 아닙니다."}

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

# ==========================================
# 유틸리티 API
# ==========================================

@app.post("/api/utils/extract-config")
async def extract_config_from_url(request: Request):
    data = await request.json()
    ws_url = data.get("websocket_url")
    
    if not ws_url:
        return {"status": "error", "message": "WebSocket URL이 제공되지 않았습니다."}
    
    try:
        from urllib.parse import urlparse, parse_qs
        
        parsed_url = urlparse(ws_url)
        query_params = parse_qs(parsed_url.query)
        
        bare_session_id = parsed_url.path.split('/')[-1]
        session_id = query_params.get('EVOSESSIONID', [''])[0]
        instance_param = query_params.get('instance', [''])[0]
        instance = instance_param.split('-')[0] if instance_param else ''
        client_version = query_params.get('client_version', [''])[0]
        
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

@app.get("/api/rooms/stats")
async def get_room_stats():
    """방 통계 정보 조회"""
    try:
        stats = room_data_manager.get_stats()
        return {
            "status": "success",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"통계 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"통계 조회 중 오류 발생: {str(e)}")

@app.post("/api/admin/cleanup")
async def cleanup_old_data(hours: int = 24):
    """오래된 데이터 정리"""
    try:
        room_data_manager.cleanup_old_data(hours)
        return {
            "status": "success",
            "message": f"{hours}시간 이전 데이터가 정리되었습니다."
        }
    except Exception as e:
        logger.error(f"데이터 정리 오류: {e}")
        raise HTTPException(status_code=500, detail=f"데이터 정리 중 오류 발생: {str(e)}")

# server.py에 추가할 API 엔드포인트

@app.get("/api/rooms/predictions/{room_id}")
async def get_room_prediction_list(room_id: str, limit: int = 20):
    """
    특정 방의 초이스픽 예측 리스트 조회 (직관적 표시)
    
    Args:
        room_id: 방 ID
        limit: 표시할 예측 개수 (기본 20개)
    """
    try:
        # 방 데이터 확인
        if room_id not in room_data_manager.room_raw_results:
            return {
                "status": "not_found",
                "message": "해당 방의 데이터를 찾을 수 없습니다.",
                "room_id": room_id
            }
        
        room_name = room_data_manager.get_room_name(room_id)
        raw_results = room_data_manager.room_raw_results[room_id]
        
        # 초이스픽 기반 연패 정보 계산
        streak_info = room_data_manager.streak_calculator.calculate_room_streak(
            room_id, room_name, raw_results
        )
        
        if not streak_info:
            return {
                "status": "insufficient_data",
                "message": "예측을 위한 데이터가 부족합니다. (최소 16개 게임 필요)",
                "room_id": room_id,
                "room_name": room_name,
                "total_games": len(raw_results)
            }
        
        # 예측 리스트 가져오기
        prediction_list = streak_info.get("prediction_list", [])
        
        # 요청된 개수만큼 제한
        if limit > 0:
            prediction_list = prediction_list[-limit:]
        
        # 콘솔 표시용 문자열 생성
        display_string = room_data_manager.streak_calculator.get_prediction_list_display(
            prediction_list, limit
        )
        
        return {
            "status": "success",
            "room_id": room_id,
            "room_name": room_name,
            "total_predictions": streak_info.get("total_predictions", 0),
            "win_rate": streak_info.get("win_rate", 0),
            "streak_count": streak_info.get("streak_count", 0),
            "filtered_results": streak_info.get("filtered_results_string", ""),
            "prediction_list": prediction_list,
            "display_string": display_string,
            "summary": {
                "total_games": len(raw_results),
                "total_predictions": len(prediction_list),
                "recent_summary": streak_info.get("prediction_summary", ""),
                "current_streak": streak_info.get("streak_count", 0)
            }
        }
    
    except Exception as e:
        logger.error(f"예측 리스트 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"예측 리스트 조회 중 오류 발생: {str(e)}")

@app.get("/api/rooms/predictions-display/{room_id}")
async def get_room_prediction_display(room_id: str, limit: int = 10):
    """
    방의 예측 리스트를 콘솔에서 보기 좋은 형태로 반환
    
    Args:
        room_id: 방 ID  
        limit: 표시할 예측 개수 (기본 10개)
    """
    try:
        prediction_response = await get_room_prediction_list(room_id, limit)
        
        if prediction_response["status"] != "success":
            return prediction_response
        
        # 콘솔 출력용 정보
        print("\n" + "="*80)
        print(f"🏠 방 정보: {prediction_response['room_name']} ({room_id})")
        print(f"📊 전체 게임: {prediction_response['summary']['total_games']}개")
        print(f"🎯 예측 개수: {prediction_response['total_predictions']}개")
        print(f"📈 성공률: {prediction_response['win_rate']}%")
        print(f"🔥 현재 연패: {prediction_response['streak_count']}회")
        print(f"🎲 전체 결과: {prediction_response['filtered_results']}")
        print(f"📝 최근 요약: {prediction_response['summary']['recent_summary']}")
        print("\n" + prediction_response['display_string'])
        print("="*80)
        
        return {
            "status": "success",
            "message": "예측 리스트가 콘솔에 출력되었습니다.",
            **prediction_response
        }
    
    except Exception as e:
        logger.error(f"예측 표시 오류: {e}")
        raise HTTPException(status_code=500, detail=f"예측 표시 중 오류 발생: {str(e)}")
        
# 기존 분석 API도 업데이트
@app.get("/api/rooms/analysis/{room_id}")
async def get_room_analysis_details(room_id: str):
    """
    특정 방의 상세 초이스픽 분석 정보 조회 (업데이트된 버전)
    """
    try:
        if room_id not in room_data_manager.room_raw_results:
            return {
                "status": "not_found", 
                "message": "해당 방의 데이터를 찾을 수 없습니다.",
                "room_id": room_id
            }
        
        room_name = room_data_manager.get_room_name(room_id)
        raw_results = room_data_manager.room_raw_results[room_id]
        
        # 업데이트된 연패 정보 계산 (예측 리스트 포함)
        streak_info = room_data_manager.streak_calculator.calculate_room_streak(
            room_id, room_name, raw_results
        )
        
        if not streak_info:
            return {
                "status": "insufficient_data",
                "message": "데이터 부족 또는 분석 실패",
                "room_id": room_id,
                "room_name": room_name,
                "total_games": len(raw_results)
            }
        
        # 추가 상세 정보
        prediction_list = streak_info.get("prediction_list", [])
        recent_predictions = prediction_list[-5:] if len(prediction_list) > 5 else prediction_list
        
        return {
            "status": "success",
            **streak_info,
            "recent_prediction_details": recent_predictions,
            "total_games": len(raw_results),
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"방 {room_id} 상세 분석 오류: {e}")
        raise HTTPException(status_code=500, detail=f"분석 중 오류 발생: {str(e)}")
    
# ==========================================
# 서버 시작
# ==========================================

if __name__ == "__main__":
    print("🎰 Vacara Auto Baccarat Server - Choice Pick Integration")
    print("🧠 초이스픽 기반 연패 계산 시스템")
    print("🔗 프론트엔드 연동 API:")
    print("   POST /api/rooms/results - 방 결과 수신 (P/B 리스트)")
    print("   GET  /api/rooms/streak/{room_id} - 초이스픽 연패 정보 조회") 
    print("   POST /api/rooms/find-streak - 연패 방 검색")
    print("   GET  /api/rooms/status - 전체 방 상태")
    print("   GET  /api/rooms/analysis/{room_id} - 방 상세 분석")
    print("📊 API 문서: http://localhost:8080/docs")
    print("=" * 50)
    
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=False)