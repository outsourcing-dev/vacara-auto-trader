import logging
from typing import List, Dict, Any, Optional
from .prediction_validator import PredictionValidator

logger = logging.getLogger(__name__)

class StreakAnalyzer:
    """
    연패 분석 메인 클래스
    모든 방의 데이터를 분석하여 연패 조건에 맞는 방들을 필터링
    """
    
    def __init__(self):
        """초기화"""
        self.logger = logger
        self.validator = PredictionValidator()
    
    def find_streak_rooms(self, room_data: Dict[str, List[Dict[str, Any]]], 
                         room_mappings: Dict[str, str], 
                         streak_count: int) -> List[Dict[str, Any]]:
        """
        연패 조건에 맞는 방들 찾기
        
        Args:
            room_data: 방별 게임 결과 데이터 {room_id: [results]}
            room_mappings: 방 ID-이름 매핑 {room_id: room_name}
            streak_count: 연패 기준
            
        Returns:
            List[Dict]: 연패 조건 만족하는 방 목록
        """
        self.logger.info(f"🔍 {streak_count}연패 방 검색 시작 (총 {len(room_data)}개 방)")
        
        streak_rooms = []
        processed_count = 0
        insufficient_data_count = 0
        
        for room_id, raw_results in room_data.items():
            processed_count += 1
            room_name = room_mappings.get(room_id, room_id)
            
            # 결과 데이터 정리 (P, B만 추출)
            filtered_results = self._filter_results(raw_results)
            
            # 최소 데이터 요구사항 확인
            min_required = 15 + (streak_count - 1)
            if len(filtered_results) < min_required:
                insufficient_data_count += 1
                self.logger.debug(
                    f"[{processed_count}/{len(room_data)}] {room_name}: "
                    f"데이터 부족 ({len(filtered_results)}/{min_required}개) → 건너뜀"
                )
                continue
            
            # 연패 예측 검증
            validation_result = self.validator.validate_streak_predictions(
                filtered_results, streak_count
            )
            
            # 상세 로그 출력
            detailed_log = self.validator.format_prediction_log(
                room_id, room_name, filtered_results, validation_result
            )
            self.logger.info(detailed_log)
            
            # 연패 조건 만족 시 결과에 추가
            if validation_result["is_streak"]:
                room_info = {
                    "room_id": room_id,
                    "room_name": room_name,
                    "streak_failures": validation_result["failures"],
                    "total_games": len(filtered_results),
                    "predictions": validation_result["predictions"],
                    "actual_results": validation_result["actual_results"],
                    "analysis_summary": self.validator.get_validation_summary(validation_result)
                }
                streak_rooms.append(room_info)
                
                self.logger.info(f"✅ [{processed_count}/{len(room_data)}] {room_name} → 연패 조건 만족!")
            else:
                self.logger.debug(f"❌ [{processed_count}/{len(room_data)}] {room_name} → 연패 조건 불만족")
        
        # 최종 결과 요약
        self.logger.info(
            f"🎯 {streak_count}연패 방 검색 완료: "
            f"조건 만족 {len(streak_rooms)}개, "
            f"데이터 부족 {insufficient_data_count}개, "
            f"총 검사 {processed_count}개"
        )
        
        # 결과를 게임 수 기준으로 정렬 (많은 순)
        streak_rooms.sort(key=lambda x: x["total_games"], reverse=True)
        
        return streak_rooms
    
    def _filter_results(self, raw_results: List[Dict[str, Any]]) -> List[str]:
        """
        원시 결과 데이터에서 P, B만 추출하여 정렬
        
        Args:
            raw_results: 원시 게임 결과 데이터
            
        Returns:
            List[str]: 정렬된 P, B 결과 리스트
        """
        try:
            # pos 기준으로 정렬
            def get_sort_key(result):
                pos = result.get("pos", [0, 0])
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    return pos[0] * 7 + pos[1]
                return 0
            
            # 결과 정렬
            sorted_results = sorted(raw_results, key=get_sort_key)
            
            # P, B만 추출
            filtered = []
            for result in sorted_results:
                c = result.get('c', '')
                if c == 'B':  # Player
                    filtered.append('P')
                elif c == 'R':  # Banker
                    filtered.append('B')
                # Tie나 기타는 무시
            
            return filtered
            
        except Exception as e:
            self.logger.error(f"결과 데이터 필터링 오류: {e}")
            return []
    
    def get_analysis_statistics(self, room_data: Dict[str, List[Dict[str, Any]]], 
                              streak_count: int) -> Dict[str, Any]:
        """
        분석 통계 정보 생성
        
        Args:
            room_data: 방별 게임 결과 데이터
            streak_count: 연패 기준
            
        Returns:
            Dict: 분석 통계 정보
        """
        total_rooms = len(room_data)
        sufficient_data_rooms = 0
        insufficient_data_rooms = 0
        min_required = 15 + (streak_count - 1)
        
        game_counts = []
        
        for room_id, raw_results in room_data.items():
            filtered_results = self._filter_results(raw_results)
            game_count = len(filtered_results)
            game_counts.append(game_count)
            
            if game_count >= min_required:
                sufficient_data_rooms += 1
            else:
                insufficient_data_rooms += 1
        
        # 통계 계산
        avg_games = sum(game_counts) / len(game_counts) if game_counts else 0
        max_games = max(game_counts) if game_counts else 0
        min_games = min(game_counts) if game_counts else 0
        
        return {
            "total_rooms": total_rooms,
            "sufficient_data_rooms": sufficient_data_rooms,
            "insufficient_data_rooms": insufficient_data_rooms,
            "min_required_games": min_required,
            "average_games": round(avg_games, 1),
            "max_games": max_games,
            "min_games": min_games,
            "streak_count": streak_count
        }
    
    def format_analysis_summary(self, streak_rooms: List[Dict[str, Any]], 
                              statistics: Dict[str, Any]) -> str:
        """
        분석 결과 요약 포맷팅
        
        Args:
            streak_rooms: 연패 조건 만족 방 목록
            statistics: 분석 통계
            
        Returns:
            str: 포맷된 요약 문자열
        """
        summary_lines = []
        summary_lines.append("=" * 50)
        summary_lines.append("📊 연패 방 분석 결과 요약")
        summary_lines.append("=" * 50)
        
        # 통계 정보
        summary_lines.append(f"🔍 검색 조건: {statistics['streak_count']}연패")
        summary_lines.append(f"📈 총 방 수: {statistics['total_rooms']}개")
        summary_lines.append(f"✅ 분석 가능: {statistics['sufficient_data_rooms']}개")
        summary_lines.append(f"❌ 데이터 부족: {statistics['insufficient_data_rooms']}개")
        summary_lines.append(f"📊 평균 게임 수: {statistics['average_games']}게임")
        summary_lines.append(f"📊 최대/최소: {statistics['max_games']}/{statistics['min_games']}게임")
        
        # 연패 방 목록
        summary_lines.append(f"\n🎯 {statistics['streak_count']}연패 조건 만족: {len(streak_rooms)}개")
        
        if streak_rooms:
            summary_lines.append("-" * 30)
            for i, room in enumerate(streak_rooms, 1):
                summary_lines.append(
                    f"{i}. {room['room_name']} "
                    f"({room['total_games']}게임, {room['streak_failures']}연패)"
                )
        else:
            summary_lines.append("조건에 맞는 방이 없습니다.")
        
        summary_lines.append("=" * 50)
        
        return "\n".join(summary_lines)