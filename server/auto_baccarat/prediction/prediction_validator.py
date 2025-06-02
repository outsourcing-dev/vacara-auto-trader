import logging
from typing import List, Dict, Any
from .choice_pick_engine import ChoicePickEngine

logger = logging.getLogger(__name__)

class PredictionValidator:
    """
    예측-결과 검증 클래스
    여러 구간의 데이터로 예측하고 실제 결과와 비교하여 연패 여부 판단
    """
    
    def __init__(self):
        """초기화"""
        self.logger = logger
        self.engine = ChoicePickEngine()
    
    def validate_streak_predictions(self, results: List[str], streak_count: int) -> Dict[str, Any]:
        """
        연패 예측 검증
        
        Args:
            results: 전체 게임 결과 리스트
            streak_count: 연패 기준 (예: 3연패)
            
        Returns:
            Dict: {
                "is_streak": bool,           # 연패 조건 만족 여부
                "predictions": List[str],    # 예측값들
                "actual_results": List[str], # 실제 결과들
                "failures": int,             # 실패 횟수
                "validation_details": List[Dict] # 검증 상세 내역
            }
        """
        # 최소 데이터 확인 (15 + streak_count)
        min_required = 15 + (streak_count - 1)
        if len(results) < min_required:
            self.logger.warning(f"데이터 부족: {len(results)}/{min_required}개 필요")
            return {
                "is_streak": False,
                "predictions": [],
                "actual_results": [],
                "failures": 0,
                "validation_details": [],
                "error": "insufficient_data"
            }
        
        predictions = []
        actual_results = []
        validation_details = []
        failures = 0
        
        # streak_count만큼 예측-검증 수행
        for i in range(streak_count):
            # 데이터 구간 설정
            start_idx = i
            end_idx = start_idx + 15
            prediction_idx = end_idx  # 예측할 위치
            
            # 예측용 데이터 추출
            prediction_data = results[start_idx:end_idx]
            actual_result = results[prediction_idx] if prediction_idx < len(results) else 'N'
            
            # 16번 픽 예측
            predicted_pick = self.engine.predict_16th_pick(prediction_data)
            
            # 예측 성공/실패 판단
            is_success = predicted_pick == actual_result and predicted_pick != 'N'
            if not is_success:
                failures += 1
            
            # 상세 정보 저장
            detail = {
                "step": i + 1,
                "data_range": f"[{start_idx}:{end_idx}]",
                "prediction_data": prediction_data.copy(),
                "predicted_pick": predicted_pick,
                "actual_result": actual_result,
                "is_success": is_success,
                "prediction_position": prediction_idx + 1  # 1-기반 위치
            }
            
            predictions.append(predicted_pick)
            actual_results.append(actual_result)
            validation_details.append(detail)
            
            self.logger.debug(
                f"예측 {i+1}단계: [{start_idx}:{end_idx}] → 예측={predicted_pick}, "
                f"실제={actual_result}, {'✅성공' if is_success else '❌실패'}"
            )
        
        # 연패 조건 만족 여부 (모든 예측이 실패해야 함)
        is_streak = failures == streak_count
        
        result = {
            "is_streak": is_streak,
            "predictions": predictions,
            "actual_results": actual_results,
            "failures": failures,
            "validation_details": validation_details
        }
        
        if is_streak:
            self.logger.info(f"✅ {streak_count}연패 조건 만족: {failures}/{streak_count} 실패")
        else:
            self.logger.debug(f"❌ {streak_count}연패 조건 불만족: {failures}/{streak_count} 실패")
        
        return result
    
    def get_validation_summary(self, validation_result: Dict[str, Any]) -> str:
        """
        검증 결과 요약 문자열 생성
        
        Args:
            validation_result: validate_streak_predictions 결과
            
        Returns:
            str: 요약 문자열
        """
        if not validation_result.get("validation_details"):
            return "검증 데이터 없음"
        
        summary_parts = []
        
        for detail in validation_result["validation_details"]:
            step = detail["step"]
            data_range = detail["data_range"]
            predicted = detail["predicted_pick"]
            actual = detail["actual_result"]
            success = "✅" if detail["is_success"] else "❌"
            
            summary_parts.append(f"{step}단계: {data_range}→{predicted}, 실제={actual} {success}")
        
        result_status = "연패 조건 만족" if validation_result["is_streak"] else "연패 조건 불만족"
        summary = f"{result_status} | " + " | ".join(summary_parts)
        
        return summary
    
    def format_prediction_log(self, room_id: str, room_name: str, results: List[str], 
                            validation_result: Dict[str, Any]) -> str:
        """
        예측 결과 로그 포맷팅
        
        Args:
            room_id: 방 ID
            room_name: 방 이름
            results: 전체 결과 데이터
            validation_result: 검증 결과
            
        Returns:
            str: 포맷된 로그 문자열
        """
        log_lines = []
        log_lines.append(f"[방 {room_id} ({room_name}) 분석]")
        
        # 전체 결과 요약
        total_count = len(results)
        p_count = results.count('P')
        b_count = results.count('B')
        log_lines.append(f"전체 결과({total_count}개): {''.join(results)} (P:{p_count}, B:{b_count})")
        
        # 검증 상세 내역
        if validation_result.get("validation_details"):
            for detail in validation_result["validation_details"]:
                step = detail["step"]
                data_range = detail["data_range"]
                prediction_data = ''.join(detail["prediction_data"])
                predicted = detail["predicted_pick"]
                actual = detail["actual_result"]
                position = detail["prediction_position"]
                status = "✅성공" if detail["is_success"] else "❌실패"
                
                log_lines.append(
                    f"{step}단계: {data_range} 데이터='{prediction_data}' → "
                    f"{position}번픽={predicted}, 실제={actual} {status}"
                )
        
        # 최종 결과
        if validation_result["is_streak"]:
            failures = validation_result["failures"]
            log_lines.append(f"🎯 {failures}연패 조건 만족 → 선택됨")
        else:
            failures = validation_result["failures"]
            total_steps = len(validation_result.get("validation_details", []))
            log_lines.append(f"❌ 연패 조건 불만족 ({failures}/{total_steps} 실패) → 제외됨")
        
        return "\n".join(log_lines)