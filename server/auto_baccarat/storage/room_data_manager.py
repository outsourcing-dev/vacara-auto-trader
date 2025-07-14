# storage/room_data_manager.py - 단순화 버전
import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from threading import Lock

# 초이스픽 기반 연패 계산기 import
from utils.choice_pick_streak_calculator import ChoicePickStreakCalculator, RoomStreakAnalyzer

logger = logging.getLogger(__name__)

class RoomDataManager:
    """방 데이터 저장 및 관리 클래스 - 현재 연패만 계산"""
    
    def __init__(self):
        self.room_data: Dict[str, Dict[str, Any]] = {}  # room_id -> room_info
        self.room_raw_results: Dict[str, List[Dict[str, Any]]] = {}  # room_id -> raw_results
        self.room_timestamps: Dict[str, datetime] = {}   # room_id -> last_update
        self.data_lock = Lock()
        
        # 필터링된 방 매핑 로드
        self.filtered_rooms = self._load_filtered_rooms()
        
        # 초이스픽 기반 연패 분석기
        self.streak_calculator = ChoicePickStreakCalculator()
        self.room_analyzer = RoomStreakAnalyzer()
        
        logger.info(f"RoomDataManager 초기화 완료: {len(self.filtered_rooms)}개 필터링된 방")
    
    def _load_filtered_rooms(self) -> Dict[str, str]:
        """filtered_room_mappings.json 파일 로드"""
        try:
            if os.path.exists("filtered_room_mappings.json"):
                with open("filtered_room_mappings.json", 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("room_mappings", {})
            else:
                logger.warning("filtered_room_mappings.json 파일을 찾을 수 없습니다.")
                return {}
        except Exception as e:
            logger.error(f"필터링된 방 매핑 로드 실패: {e}")
            return {}
    
    def is_filtered_room(self, room_id: str) -> bool:
        """필터링된 방인지 확인"""
        return room_id in self.filtered_rooms
    
    def get_room_name(self, room_id: str) -> str:
        """방 ID로 방 이름 조회"""
        return self.filtered_rooms.get(room_id, room_id)
    
    def update_room_results(self, room_id: str, room_name: str, recent_results: List[str], round_number: int) -> bool:
        """
        방 결과 업데이트 (프론트엔드에서 P/B 문자열 리스트로 전송)
        """
        if not self.is_filtered_room(room_id):
            logger.debug(f"필터링되지 않은 방 무시: {room_id}")
            return False
        
        with self.data_lock:
            # 방 기본 정보 업데이트
            self.room_data[room_id] = {
                "room_id": room_id,
                "room_name": room_name,
                "round_number": round_number,
                "total_results": len(recent_results),
                "last_update": datetime.now().isoformat()
            }
            
            # P/B 문자열을 원시 결과 형태로 변환
            raw_results = []
            for i, result in enumerate(recent_results):
                raw_results.append({
                    "pos": [i // 7, i % 7],  # 임시 pos 값
                    "c": "B" if result == "P" else "R" if result == "B" else "T"  # P->B(Player), B->R(Banker)
                })
            
            # 원시 결과 저장 (최대 100개까지)
            self.room_raw_results[room_id] = raw_results[-100:] if len(raw_results) > 100 else raw_results
            self.room_timestamps[room_id] = datetime.now()
            
            logger.info(f"방 데이터 업데이트: {room_name} ({room_id}) - {len(recent_results)}개 결과")
            return True
    
    def get_room_streak_info(self, room_id: str) -> Optional[Dict[str, Any]]:
        """현재 연패 정보만 반환"""
        if room_id not in self.room_raw_results:
            return None
        
        room_name = self.get_room_name(room_id)
        raw_results = self.room_raw_results[room_id]
        
        # 연패 계산
        streak_info = self.streak_calculator.calculate_room_streak(room_id, room_name, raw_results)
        
        return streak_info  # None이거나 {"room_id": ..., "room_name": ..., "streak_count": ...}
    
    def find_streak_rooms(self, min_streak: int = 3) -> List[Dict[str, Any]]:
        """조건에 맞는 연패 방 찾기 - 방이름과 현재연패수만 반환"""
        with self.data_lock:
            # 원시 결과 데이터를 올바른 형태로 변환
            rooms_data = {}
            for room_id, raw_results in self.room_raw_results.items():
                rooms_data[room_id] = {"results": raw_results}
            
            # 연패 분석
            streak_rooms = self.room_analyzer.analyze_rooms(
                rooms_data, 
                self.filtered_rooms, 
                min_streak
            )
        
        logger.info(f"{min_streak}연패 이상 방 {len(streak_rooms)}개 발견")
        return streak_rooms
    
    def cleanup_old_data(self, hours: int = 24):
        """오래된 데이터 정리"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self.data_lock:
            expired_rooms = []
            
            for room_id, timestamp in self.room_timestamps.items():
                if timestamp < cutoff_time:
                    expired_rooms.append(room_id)
            
            for room_id in expired_rooms:
                self.room_data.pop(room_id, None)
                self.room_raw_results.pop(room_id, None)
                self.room_timestamps.pop(room_id, None)
            
            if expired_rooms:
                logger.info(f"{len(expired_rooms)}개 만료된 방 데이터 정리 완료")
    
    def get_stats(self) -> Dict[str, Any]:
        """간단한 통계 정보만 반환"""
        with self.data_lock:
            total_rooms = len(self.room_data)
            total_filtered_rooms = len(self.filtered_rooms)
            
            streak_counts = {"3+": 0, "5+": 0, "7+": 0}
            
            for room_id in self.room_raw_results:
                streak_info = self.get_room_streak_info(room_id)
                if streak_info:
                    streak = streak_info["streak_count"]
                    if streak >= 3:
                        streak_counts["3+"] += 1
                    if streak >= 5:
                        streak_counts["5+"] += 1
                    if streak >= 7:
                        streak_counts["7+"] += 1
            
            return {
                "total_rooms_monitored": total_rooms,
                "total_filtered_rooms": total_filtered_rooms,
                "streak_rooms": streak_counts,
                "last_update": datetime.now().isoformat()
            }