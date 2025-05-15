import os
import sys
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

# 상위 디렉토리 모듈 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("prediction_engine")

class PredictionEngine:
    """바카라 게임 예측 엔진"""
    
    def __init__(self):
        self.algorithm_settings: Dict[str, Dict[str, Any]] = {}  # user_id -> settings
    
    def set_algorithm_settings(self, user_id: str, settings: Dict[str, Any]):
        """알고리즘 설정 저장"""
        if user_id not in self.algorithm_settings:
            # 기본 설정
            self.algorithm_settings[user_id] = {
                "algorithm": "pattern_recognition",  # 기본 알고리즘
                "sample_size": 15,                  # 패턴 분석 샘플 크기
                "confidence_threshold": 0.6          # 신뢰도 기준
            }
        
        # 제공된 설정으로 업데이트
        self.algorithm_settings[user_id].update(settings)
    
    def get_algorithm_settings(self, user_id: str) -> Dict[str, Any]:
        """알고리즘 설정 반환"""
        if user_id not in self.algorithm_settings:
            # 기본 설정
            self.algorithm_settings[user_id] = {
                "algorithm": "pattern_recognition",
                "sample_size": 15,
                "confidence_threshold": 0.6
            }
        
        return self.algorithm_settings[user_id]
    
    def predict_next_outcome(self, results: List[Dict[str, Any]], settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """다음 게임 결과 예측
        
        Args:
            results: 지금까지의 게임 결과 목록
            settings: 예측 알고리즘 설정 (기본값 사용 시 None)
            
        Returns:
            예측 결과 (prediction, confidence, method 등)
        """
        if not settings:
            settings = {
                "algorithm": "pattern_recognition",
                "sample_size": 15,
                "confidence_threshold": 0.6
            }
        
        # 충분한 결과가 없으면 예측 불가
        if len(results) < settings["sample_size"]:
            return {
                "prediction": None,
                "confidence": 0.0,
                "method": "insufficient_data",
                "message": f"충분한 데이터가 없습니다. 필요: {settings['sample_size']}, 현재: {len(results)}"
            }
        
        # 알고리즘 선택 및 실행
        algorithm = settings["algorithm"]
        
        if algorithm == "pattern_recognition":
            return self._pattern_recognition(results, settings)
        elif algorithm == "streak_analysis":
            return self._streak_analysis(results, settings)
        elif algorithm == "frequency_analysis":
            return self._frequency_analysis(results, settings)
        else:
            logger.warning(f"알 수 없는 알고리즘: {algorithm}, 기본 패턴 인식 사용")
            return self._pattern_recognition(results, settings)
    
    def _pattern_recognition(self, results: List[Dict[str, Any]], settings: Dict[str, Any]) -> Dict[str, Any]:
        """패턴 인식 알고리즘
        
        최근 N개 결과의 패턴이 과거에 발생했던 패턴과 일치하는지 확인하고,
        해당 패턴 이후에 나왔던 결과를 예측값으로 사용
        """
        sample_size = settings["sample_size"]
        confidence_threshold = settings["confidence_threshold"]
        
        # 결과 정렬: x*7 + y 기준 (오래된 것부터 최신까지)
        sorted_results = sorted(results, key=lambda x: (x["pos"][0] * 7 + x["pos"][1]))
        
        # 최근 N개 결과 추출
        recent_pattern = []
        for result in sorted_results[-sample_size:]:
            c = result.get('c', '')
            if c == 'B':  # 플레이어
                recent_pattern.append('P')
            elif c == 'R':  # 뱅커
                recent_pattern.append('B')
            else:  # 타이 등
                recent_pattern.append('T')
        
        # 패턴 매칭 시도
        matches = []
        for i in range(len(sorted_results) - sample_size - 1):
            pattern = []
            for j in range(sample_size):
                if i + j >= len(sorted_results):
                    break
                
                c = sorted_results[i + j].get('c', '')
                if c == 'B':  # 플레이어
                    pattern.append('P')
                elif c == 'R':  # 뱅커
                    pattern.append('B')
                else:  # 타이 등
                    pattern.append('T')
            
            # 패턴 일치 확인
            if pattern == recent_pattern and i + sample_size < len(sorted_results):
                next_result = sorted_results[i + sample_size]
                c = next_result.get('c', '')
                if c == 'B':  # 플레이어
                    matches.append('P')
                elif c == 'R':  # 뱅커
                    matches.append('B')
                else:  # 타이 등
                    matches.append('T')
        
        # 예측 결과 계산
        if not matches:
            return {
                "prediction": None,
                "confidence": 0.0,
                "method": "pattern_recognition",
                "message": "일치하는 패턴을 찾을 수 없습니다."
            }
        
        # 가장 빈번한 다음 결과 찾기
        player_count = matches.count('P')
        banker_count = matches.count('B')
        tie_count = matches.count('T')
        
        total_matches = len(matches)
        if player_count > banker_count and player_count > tie_count:
            confidence = player_count / total_matches
            prediction = 'player'
        elif banker_count > player_count and banker_count > tie_count:
            confidence = banker_count / total_matches
            prediction = 'banker'
        else:
            confidence = tie_count / total_matches
            prediction = 'tie'
        
        # 충분한 신뢰도인지 확인
        if confidence < confidence_threshold:
            return {
                "prediction": prediction,
                "confidence": confidence,
                "method": "pattern_recognition",
                "message": f"낮은 신뢰도 예측: {confidence:.2f} < {confidence_threshold}",
                "matches": {"player": player_count, "banker": banker_count, "tie": tie_count}
            }
        
        return {
            "prediction": prediction,
            "confidence": confidence,
            "method": "pattern_recognition",
            "matches": {"player": player_count, "banker": banker_count, "tie": tie_count}
        }
    
    def _streak_analysis(self, results: List[Dict[str, Any]], settings: Dict[str, Any]) -> Dict[str, Any]:
        """연속 패턴 분석 알고리즘
        
        현재 연속된 결과가 다음에도 계속될 확률 예측
        """
        sample_size = min(settings["sample_size"], len(results))
        confidence_threshold = settings["confidence_threshold"]
        
        # 결과 정렬: x*7 + y 기준 (오래된 것부터 최신까지)
        sorted_results = sorted(results, key=lambda x: (x["pos"][0] * 7 + x["pos"][1]))
        
        # 현재 연속 패턴 확인
        current_streak = 0
        streak_type = None
        
        for i in range(len(sorted_results) - 1, -1, -1):
            result = sorted_results[i]
            c = result.get('c', '')
            
            if streak_type is None:
                # 첫 결과 설정
                if c == 'B':  # 플레이어
                    streak_type = 'player'
                    current_streak = 1
                elif c == 'R':  # 뱅커
                    streak_type = 'banker'
                    current_streak = 1
                else:  # 타이 등
                    continue  # 타이는 연속으로 세지 않음
            else:
                # 연속 확인
                if (c == 'B' and streak_type == 'player') or (c == 'R' and streak_type == 'banker'):
                    current_streak += 1
                else:
                    break
        
        # 연속 패턴이 없으면 예측 불가
        if current_streak == 0 or streak_type is None:
            return {
                "prediction": None,
                "confidence": 0.0,
                "method": "streak_analysis",
                "message": "현재 연속 패턴이 없습니다."
            }
        
        # 과거에 이 길이의 연속이 다음에도 연속되었는지 확인
        continued_count = 0
        broken_count = 0
        
        for i in range(len(sorted_results) - 1):
            streak = 0
            s_type = None
            
            # 연속 패턴 검색
            for j in range(i, -1, -1):
                result = sorted_results[j]
                c = result.get('c', '')
                
                if s_type is None:
                    if c == 'B':  # 플레이어
                        s_type = 'player'
                        streak = 1
                    elif c == 'R':  # 뱅커
                        s_type = 'banker'
                        streak = 1
                    else:
                        break
                else:
                    if (c == 'B' and s_type == 'player') or (c == 'R' and s_type == 'banker'):
                        streak += 1
                    else:
                        break
                
                if streak == current_streak:
                    # 다음 결과 확인
                    if i + 1 < len(sorted_results):
                        next_result = sorted_results[i + 1]
                        next_c = next_result.get('c', '')
                        
                        if (next_c == 'B' and s_type == 'player') or (next_c == 'R' and s_type == 'banker'):
                            continued_count += 1
                        else:
                            broken_count += 1
                    
                    break
        
        # 예측 결과 계산
        total_occurences = continued_count + broken_count
        if total_occurences == 0:
            return {
                "prediction": None,
                "confidence": 0.0,
                "method": "streak_analysis",
                "message": f"{current_streak}번의 {streak_type} 연속 패턴의 과거 사례가 없습니다."
            }
        
        # 지금까지의 연속이 계속될 확률
        continuation_probability = continued_count / total_occurences
        
        if continuation_probability >= confidence_threshold:
            # 연속 가능성이 높음
            prediction = streak_type
            message = f"{current_streak}번의 {streak_type} 연속은 계속될 가능성이 높습니다."
        else:
            # 연속이 깨질 가능성이 높음
            prediction = 'banker' if streak_type == 'player' else 'player'
            message = f"{current_streak}번의 {streak_type} 연속은 깨질 가능성이 높습니다."
            continuation_probability = 1 - continuation_probability  # 반전
        
        return {
            "prediction": prediction,
            "confidence": continuation_probability,
            "method": "streak_analysis",
            "current_streak": current_streak,
            "streak_type": streak_type,
            "stats": {"continued": continued_count, "broken": broken_count},
            "message": message
        }
    
    def _frequency_analysis(self, results: List[Dict[str, Any]], settings: Dict[str, Any]) -> Dict[str, Any]:
        """빈도 분석 알고리즘
        
        최근 일정 기간 동안의 플레이어/뱅커 출현 빈도 분석으로 다음 결과 예측
        """
        sample_size = min(settings["sample_size"], len(results))
        confidence_threshold = settings["confidence_threshold"]
        
        # 결과 정렬: x*7 + y 기준 (오래된 것부터 최신까지)
        sorted_results = sorted(results, key=lambda x: (x["pos"][0] * 7 + x["pos"][1]))
        
        # 최근 N개 결과의 빈도 분석
        recent_results = sorted_results[-sample_size:]
        
        player_count = 0
        banker_count = 0
        tie_count = 0
        
        for result in recent_results:
            c = result.get('c', '')
            if c == 'B':  # 플레이어
                player_count += 1
            elif c == 'R':  # 뱅커
                banker_count += 1
            else:  # 타이 등
                tie_count += 1
        
        # 빈도 기반 확률 계산
        total_valid = player_count + banker_count  # 타이 제외
        if total_valid == 0:
            return {
                "prediction": None,
                "confidence": 0.0,
                "method": "frequency_analysis",
                "message": "유효한 결과가 없습니다."
            }
        
        player_prob = player_count / total_valid
        banker_prob = banker_count / total_valid
        
        # 빈도 분석 전략:
        # 1. 뚜렷한 편향이 있으면(> threshold) 그 반대 쪽이 나올 가능성 높음
        # 2. 비슷하게 나왔으면 더 적게 나온 쪽이 나올 가능성 약간 높음
        
        imbalance = abs(player_prob - banker_prob)
        
        if imbalance > 0.2:  # 뚜렷한 불균형
            # 많이 나온 쪽의 반대가 나올 가능성
            if player_prob > banker_prob:
                prediction = 'banker'
                confidence = 0.5 + (imbalance / 2)  # 0.6 ~ 0.75 범위
            else:
                prediction = 'player'
                confidence = 0.5 + (imbalance / 2)  # 0.6 ~ 0.75 범위
        else:  # 비슷한 빈도
            # 약간 더 적게 나온 쪽이 나올 확률 살짝 높음
            if player_prob < banker_prob:
                prediction = 'player'
                confidence = 0.5 + (imbalance / 4)  # 0.5 ~ 0.55 범위
            else:
                prediction = 'banker'
                confidence = 0.5 + (imbalance / 4)  # 0.5 ~ 0.55 범위
        
        return {
            "prediction": prediction,
            "confidence": confidence,
            "method": "frequency_analysis",
            "stats": {"player": player_count, "banker": banker_count, "tie": tie_count},
            "frequencies": {"player": player_prob, "banker": banker_prob}
        }