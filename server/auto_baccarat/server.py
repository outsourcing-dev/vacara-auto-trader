import os
import sys
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.room_data_manager import RoomDataManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("baccarat_server")

app = FastAPI(title="Vacara Auto Baccarat API Server - Simplified")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 글로벌 데이터 매니저
room_data_manager = RoomDataManager()

# 요청 모델들
class RoomResultsRequest(BaseModel):
    room_id: str
    mapped_room_name: str
    all_results: List[str]  # P/B 리스트
    total_results: int
    latest_result: str

class StreakVerificationRequest(BaseModel):
    room_id: str
    current_results: List[str]  # 현재 방의 모든 결과 (P/B)
    expected_streak: int  # 서버에서 예상한 연패 수

class PredictionRequest(BaseModel):
    room_id: str
    current_results: List[str]  # 최근 결과 (P/B)

# ==========================================
# 핵심 API 엔드포인트
# ==========================================

@app.get("/api/status")
async def get_status():
    stats = room_data_manager.get_stats()
    return {
        "status": "running",
        "version": "3.0.0-simplified",
        "timestamp": datetime.now().isoformat(),
        "room_stats": stats
    }

@app.post("/api/rooms/calculate-streak")
async def calculate_room_streak(request: RoomResultsRequest):
    """
    방 결과를 받아서 현재 연패 수 계산 (프론트엔드용)
    """
    try:
        # R/B를 P/B로 변환
        converted_results = []
        for result in request.all_results:
            if result == "R":  # Banker
                converted_results.append("B")
            elif result == "B":  # Player  
                converted_results.append("P")
        
        # 데이터 업데이트
        success = room_data_manager.update_room_results(
            room_id=request.room_id,
            room_name=request.mapped_room_name,
            recent_results=converted_results,
            round_number=request.total_results
        )
        
        if not success:
            return {
                "status": "filtered_out",
                "message": "필터링되지 않은 방입니다.",
                "current_streak": 0
            }
        
        # 연패 계산
        streak_info = room_data_manager.get_room_streak_info(request.room_id)
        current_streak = streak_info["streak_count"] if streak_info else 0
        
        logger.info(f"🔥 {request.mapped_room_name}: {current_streak}연패")
        
        return {
            "status": "success",
            "room_name": request.mapped_room_name,
            "current_streak": current_streak,
            "total_results": request.total_results
        }
        
    except Exception as e:
        logger.error(f"연패 계산 오류: {e}")
        raise HTTPException(status_code=500, detail=f"연패 계산 중 오류: {str(e)}")

@app.post("/api/rooms/verify-and-predict")
async def verify_streak_and_get_prediction(request: StreakVerificationRequest):
    """
    ⭐ 핵심 API: 연패 검증 + 다음 예측값 반환
    """
    try:
        # 1. 현재 방 데이터 업데이트
        room_name = room_data_manager.get_room_name(request.room_id)
        room_data_manager.update_room_results(
            room_id=request.room_id,
            room_name=room_name,
            recent_results=request.current_results,
            round_number=len(request.current_results)
        )
        
        # 2. 연패 재계산
        streak_info = room_data_manager.get_room_streak_info(request.room_id)
        current_streak = streak_info["streak_count"] if streak_info else 0
        
        logger.info(f"🔍 {room_name} 연패 검증: 예상 {request.expected_streak} vs 실제 {current_streak}")
        
        # 3. 연패가 끊어졌거나 조건 미달
        if current_streak < 3:  # 최소 3연패 기준
            return {
                "status": "streak_broken",
                "message": "연패가 끊어졌거나 조건에 맞지 않습니다.",
                "current_streak": current_streak,
                "should_exit_room": True,
                "next_prediction": None
            }
        
        # 4. 연패 지속중 - 다음 예측값 생성
        next_prediction = room_data_manager._generate_next_prediction(request.current_results)
        
        return {
            "status": "streak_continues",
            "message": f"연패 지속중 - 베팅 진행",
            "current_streak": current_streak,
            "should_exit_room": False,
            "next_prediction": next_prediction,
            "room_name": room_name
        }
        
    except Exception as e:
        logger.error(f"연패 검증/예측 오류: {e}")
        return {
            "status": "error",
            "message": f"처리 중 오류 발생: {str(e)}",
            "should_exit_room": True,
            "next_prediction": None
        }

@app.post("/api/rooms/get-prediction")
async def get_next_prediction(request: PredictionRequest):
    """
    현재 결과를 기반으로 다음 예측값만 반환
    """
    try:
        next_prediction = room_data_manager._generate_next_prediction(request.current_results)
        
        return {
            "status": "success",
            "next_prediction": next_prediction,
            "data_length": len(request.current_results)
        }
        
    except Exception as e:
        logger.error(f"예측 생성 오류: {e}")
        raise HTTPException(status_code=500, detail=f"예측 생성 중 오류: {str(e)}")

@app.post("/api/rooms/find-streak")
async def find_streak_rooms(min_streak: int = 3):
    """
    조건에 맞는 연패 방 목록 조회
    """
    try:
        streak_rooms = room_data_manager.find_streak_rooms(min_streak)
        
        return {
            "status": "success",
            "streak_rooms": streak_rooms,
            "total_found": len(streak_rooms),
            "min_streak": min_streak
        }
    
    except Exception as e:
        logger.error(f"연패 방 검색 오류: {e}")
        raise HTTPException(status_code=500, detail=f"연패 방 검색 중 오류: {str(e)}")

# ==========================================
# 유틸리티 API
# ==========================================

@app.get("/api/rooms/stats")
async def get_room_stats():
    """방 통계 정보"""
    try:
        stats = room_data_manager.get_stats()
        return {"status": "success", "stats": stats}
    except Exception as e:
        logger.error(f"통계 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"통계 조회 중 오류: {str(e)}")

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
        raise HTTPException(status_code=500, detail=f"데이터 정리 중 오류: {str(e)}")

if __name__ == "__main__":
    print("🎰 Vacara Auto Baccarat Server - Simplified Version")
    print("🧠 핵심 API 엔드포인트:")
    print("   POST /api/rooms/calculate-streak - 연패 계산")
    print("   POST /api/rooms/verify-and-predict - ⭐ 연패 검증 + 예측값")
    print("   POST /api/rooms/get-prediction - 예측값만 반환")
    print("   POST /api/rooms/find-streak - 연패 방 검색")
    print("📊 API 문서: http://localhost:8080/docs")
    print("=" * 50)
    
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=False)