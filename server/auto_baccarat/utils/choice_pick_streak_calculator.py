import logging
from typing import List, Dict, Any, Optional
from utils.choice_pick import ChoicePickSystem

logger = logging.getLogger(__name__)

class ChoicePickStreakCalculator:
    """
    초이스픽 기반 연패 계산기 - 현재 연패 수만 계산
    """
    
    def __init__(self):
        self.choice_pick_system = ChoicePickSystem()
    
    def calculate_room_streak(self, room_id: str, room_name: str, raw_results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        방의 현재 연패 정보 계산 (단순화 버전)
        
        Args:
            room_id: 방 ID
            room_name: 방 이름  
            raw_results: 원시 게임 결과 데이터
            
        Returns:
            연패 정보 Dict 또는 None (데이터 부족시)
        """
        try:
            # 1. 원시 데이터를 P/B 결과로 변환
            filtered_results = self._filter_and_sort_results(raw_results)
            
            if len(filtered_results) < 16:  # 최소 16개 필요
                return None
            
            # 2. 예측 결과 계산
            prediction_results = self._calculate_predictions(filtered_results)
            
            if not prediction_results:
                return None
            
            # 3. 현재 연패 수만 계산
            current_streak = self._calculate_streak_count(prediction_results)
            
            # 4. 단순한 결과만 반환
            return {
                "room_id": room_id,
                "room_name": room_name,
                "streak_count": current_streak
            }
            
        except Exception as e:
            logger.error(f"방 {room_name} 연패 계산 오류: {e}")
            return None
    
    def _filter_and_sort_results(self, raw_results: List[Dict[str, Any]]) -> List[str]:
        """
        원시 결과를 P/B로 필터링 및 정렬
        """
        try:
            def get_sort_key(result):
                pos = result.get("pos", [0, 0])
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    return pos[0] * 7 + pos[1]
                return 0
            
            sorted_results = sorted(raw_results, key=get_sort_key)
            
            filtered = []
            for result in sorted_results:
                c = result.get('c', '')
                if c == 'B':  # Player 승리
                    filtered.append('P')
                elif c == 'R':  # Banker 승리  
                    filtered.append('B')
            
            return filtered
            
        except Exception as e:
            logger.error(f"결과 필터링 오류: {e}")
            return []
    
    def _calculate_predictions(self, results: List[str]) -> List[Dict[str, Any]]:
        """
        초이스픽을 사용하여 예측 결과 계산
        """
        predictions = []
        
        # 디버깅: 입력 데이터 로그
        logger.info(f"🎯 예측 계산 시작: 총 {len(results)}개 결과")
        logger.info(f"📊 전체 결과: {''.join(results)}")
        
        for i in range(15, len(results)):
            try:
                prediction_data = results[i-15:i]
                actual_result = results[i]
                
                choice_system = ChoicePickSystem()
                choice_system.add_multiple_results(prediction_data)
                
                if choice_system.has_sufficient_data():
                    predicted_pick = choice_system.generate_choice_pick()
                    is_win = predicted_pick == actual_result
                    
                    # 디버깅: 각 예측 과정 로그
                    result_text = "승" if is_win else "패"
                    logger.info(f"게임 {i+1}: {predicted_pick} vs {actual_result} = {result_text}")
                    
                    predictions.append({
                        "is_win": is_win
                    })
                
            except Exception as e:
                logger.warning(f"예측 계산 오류 (위치 {i+1}): {e}")
                continue
        
        logger.info(f"✅ 총 {len(predictions)}개 예측 완료")
        return predictions

    def _calculate_streak_count(self, prediction_results: List[Dict[str, Any]]) -> int:
        """
        현재 진행중인 연패 수 계산 (최신부터 역순)
        """
        if not prediction_results:
            return 0
        
        current_streak = 0
        
        # 디버깅: 최근 예측 결과들 로그
        recent_results = [("승" if p["is_win"] else "패") for p in prediction_results[-10:]]
        logger.info(f"📈 최근 10개 예측 결과: {' '.join(recent_results)}")
        
        # 최신 결과부터 역순으로 연패 계산
        for i, prediction in enumerate(reversed(prediction_results)):
            if not prediction["is_win"]:  # 예측 실패 (패배)
                current_streak += 1
                logger.info(f"연패 {current_streak}: 뒤에서 {i+1}번째 게임 패배")
            else:  # 예측 성공 (승리) - 연패 중단
                logger.info(f"연패 중단: 뒤에서 {i+1}번째 게임 승리")
                break
        
        logger.info(f"🔥 최종 연패 수: {current_streak}")
        return current_streak

class RoomStreakAnalyzer:
    """
    여러 방의 연패 정보를 분석하는 클래스 - 단순화 버전
    """
    
    def __init__(self):
        self.calculator = ChoicePickStreakCalculator()
    
    def analyze_rooms(self, rooms_data: Dict[str, Dict[str, Any]], 
                     room_mappings: Dict[str, str], 
                     min_streak: int = 3) -> List[Dict[str, Any]]:
        """
        여러 방의 연패 정보 분석 - 조건에 맞는 방만 반환
        
        Args:
            rooms_data: 방별 데이터
            room_mappings: 방 ID-이름 매핑
            min_streak: 최소 연패 수
            
        Returns:
            조건에 맞는 방 목록 (방이름 + 현재연패수만)
        """
        streak_rooms = []
        
        for room_id, room_data in rooms_data.items():
            room_name = room_mappings.get(room_id, room_id)
            raw_results = room_data.get("results", [])
            
            # 연패 계산
            streak_info = self.calculator.calculate_room_streak(room_id, room_name, raw_results)
            
            if streak_info and streak_info["streak_count"] >= min_streak:
                streak_rooms.append({
                    "room_name": streak_info["room_name"],
                    "current_streak": streak_info["streak_count"]
                })
        
        # 연패 수 기준 내림차순 정렬
        streak_rooms.sort(key=lambda x: x["current_streak"], reverse=True)
        
        logger.info(f"분석 완료: {len(streak_rooms)}개 방이 {min_streak}연패 이상 조건 만족")
        
        return streak_rooms