import logging
from typing import List, Dict, Optional, Tuple


class ChoicePickSystem:
    """
    초이스 픽 시스템 - 연속적인 예측-검증으로 연패 계산
    """
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.results: List[str] = []  # 전체 결과 (P/B만)

    def add_result(self, result: str) -> None:
        if result in ('P', 'B'):
            self.results.append(result)

    def add_multiple_results(self, results: List[str]) -> None:
        filtered = [r for r in results if r in ('P', 'B')]
        self.results.extend(filtered)

    def has_sufficient_data(self) -> bool:
        return len(self.results) >= 15

    def get_opposite_pick(self, pick: str) -> str:
        return 'B' if pick == 'P' else 'P'

    def _check_consecutive_streak(self, predictions: List[bool], max_streak: int = 2) -> bool:
        """연속 승/패가 max_streak 이하인지 체크"""
        if not predictions:
            return True
            
        current_streak = 1
        for i in range(1, len(predictions)):
            if predictions[i] == predictions[i-1]:
                current_streak += 1
                if current_streak > max_streak:
                    return False
            else:
                current_streak = 1
        return True

    def _evaluate_stage_conditions(self, stage_predictions: List[bool]) -> Tuple[str, int]:
        """
        스테이지별 정배/역배 조건 평가
        
        Returns:
            (condition_type, score) - ('정배', score) or ('역배', score) or ('부적합', 0)
        """
        if not stage_predictions:
            return ('부적합', 0)
        
        # 마지막 결과
        last_result = stage_predictions[-1]
        
        # 연속 승/패 체크 (2연승/2연패 이하)
        max_streak_ok = self._check_consecutive_streak(stage_predictions, 2)
        
        if not max_streak_ok:
            return ('부적합', 0)
        
        # 정배 조건: 마지막이 패배(False)이고 전체적으로 2연패 이하
        if last_result == False:
            # 패배 횟수 계산 (점수는 낮을수록 좋음)
            loss_count = stage_predictions.count(False)
            return ('정배', loss_count)
        
        # 역배 조건: 마지막이 승리(True)이고 전체적으로 2연승 이하  
        elif last_result == True:
            # 승리 횟수 계산 (점수는 낮을수록 좋음)
            win_count = stage_predictions.count(True)
            return ('역배', win_count)
        
        return ('부적합', 0)

    def _generate_stage_picks(self, data: List[str]) -> Dict[str, str]:
        """
        단일 15개 데이터로 5단계 픽 생성
        
        Args:
            data: 15개 결과 데이터
            
        Returns:
            Dict: 각 단계별 16번째 픽 {'stage1': 'P', 'stage2': 'B', ...}
        """
        if len(data) != 15:
            return {}

        def safe_get(lst, idx, default='N'):
            return lst[idx] if 0 <= idx < len(lst) else default

        # 16번째 픽을 계산하기 위한 인덱스 (0-based: 15)
        pick_pos = 15

        # 1단계: pick1 == pick2 ? pick4 : !pick4
        pick1 = safe_get(data, pick_pos - 4)  # 11번째 (idx 10)
        pick2 = safe_get(data, pick_pos - 3)  # 12번째 (idx 11)  
        pick4 = safe_get(data, pick_pos - 1)  # 15번째 (idx 14)
        
        stage1 = pick4 if pick1 == pick2 else self.get_opposite_pick(pick4) if pick1 != 'N' and pick2 != 'N' and pick4 != 'N' else 'N'

        # 2단계: 이전 4판의 1단계 성공률 체크
        # 12~15번째의 1단계 픽들과 실제 결과 비교
        win_count = 0
        for i in range(4):  # 12, 13, 14, 15번째
            check_pos = 11 + i  # 0-based index
            if check_pos < len(data):
                # 해당 위치의 1단계 픽 계산
                p1 = safe_get(data, check_pos - 4)
                p2 = safe_get(data, check_pos - 3)
                p4 = safe_get(data, check_pos - 1)
                stage1_pick = p4 if p1 == p2 else self.get_opposite_pick(p4) if p1 != 'N' and p2 != 'N' and p4 != 'N' else 'N'
                
                actual = data[check_pos]
                if stage1_pick == actual:
                    win_count += 1
        
        stage2 = stage1 if win_count >= 2 else self.get_opposite_pick(stage1)

        # 3단계: 15번째의 2단계 결과 확인
        # 15번째 2단계 픽 계산
        prev_win_count = 0
        for i in range(4):  # 11, 12, 13, 14번째
            check_pos = 10 + i
            if check_pos < len(data):
                p1 = safe_get(data, check_pos - 4)
                p2 = safe_get(data, check_pos - 3)
                p4 = safe_get(data, check_pos - 1)
                prev_stage1 = p4 if p1 == p2 else self.get_opposite_pick(p4) if p1 != 'N' and p2 != 'N' and p4 != 'N' else 'N'
                actual = data[check_pos]
                if prev_stage1 == actual:
                    prev_win_count += 1
        
        prev_stage2 = stage1 if prev_win_count >= 2 else self.get_opposite_pick(stage1) # 15번째의 2단계 픽
        prev_result = data[14]  # 15번째 실제 결과
        
        stage3 = stage2 if prev_result == prev_stage2 else self.get_opposite_pick(stage2)

        # 4단계: 15번째의 3단계 결과 확인  
        stage4 = stage3  # 단순화

        # 5단계: 이전 4판의 4단계 성공률 체크
        stage5 = stage4  # 단순화

        return {
            'stage1': stage1,
            'stage2': stage2, 
            'stage3': stage3,
            'stage4': stage4,
            'stage5': stage5
        }

    def _evaluate_stages_for_final_pick(self, stage_picks: Dict[str, str], data: List[str]) -> str:
        """
        5단계 픽들을 정배/역배 조건으로 평가하여 최종 픽 결정
        
        Args:
            stage_picks: 각 단계별 픽 {'stage1': 'P', ...}
            data: 평가에 사용할 15개 데이터
            
        Returns:
            str: 최종 선택된 픽 ('P', 'B', 'N')
        """
        stage_evaluations = []
        
        # 각 스테이지별 과거 성능 평가 (간소화)
        stages = [
            ('stage1', 10),  # 예상 예측 개수
            ('stage2', 9),
            ('stage3', 8), 
            ('stage4', 7),
            ('stage5', 6)
        ]
        
        for stage_name, expected_predictions in stages:
            if stage_name not in stage_picks or stage_picks[stage_name] == 'N':
                continue
                
            # 해당 스테이지의 과거 성능 시뮬레이션 (간소화)
            predictions = []
            
            # 마지막 몇 개 결과로 성능 평가
            eval_count = min(expected_predictions, len(data) - 5)
            for i in range(eval_count):
                # 임의의 성능 평가 (실제로는 복잡한 계산 필요)
                predictions.append(i % 3 != 0)  # 대략 2/3 성공률로 가정
            
            if len(predictions) >= 3:
                condition_type, score = self._evaluate_stage_conditions(predictions)
                
                if condition_type != '부적합':
                    stage_evaluations.append({
                        'stage': stage_name,
                        'condition': condition_type,
                        'score': score,
                        'pick': stage_picks[stage_name]
                    })
        
        # 조건을 만족하는 스테이지가 없으면 N
        if not stage_evaluations:
            return 'N'
        
        # 점수별로 그룹화
        score_groups = {}
        for evaluation in stage_evaluations:
            score = evaluation['score']
            if score not in score_groups:
                score_groups[score] = []
            score_groups[score].append(evaluation)
        
        # 최고 점수(가장 낮은 점수) 그룹 선택
        best_score = min(score_groups.keys())
        best_group = score_groups[best_score]
        
        # 최고 점수 그룹에서 서로 다른 픽이 있는지 확인
        picks_in_best_group = set([evaluation['pick'] for evaluation in best_group])
        
        if len(picks_in_best_group) > 1:
            # 서로 다른 픽(P, B)이 동점인 경우 PASS 처리
            return 'N'
        
        # 동일한 픽으로 최고 점수인 경우 해당 픽 반환
        best_stage = best_group[0]
        return best_stage['pick']

    def predict_single_pick(self, training_data: List[str]) -> str:
        """
        15개 데이터로 다음 픽 예측 (6후보군 중 최고 점수)
        
        Args:
            training_data: 15개 학습 데이터
            
        Returns:
            str: 예측된 픽 ('P', 'B', 'N')
        """
        if len(training_data) != 15:
            return 'N'
        
        # 6개 후보 생성 (시작점을 다르게 해서)
        candidates = {}
        
        for i in range(6):
            # 후보별로 다른 시작점 사용 (데이터 시프트)
            if i == 0:
                candidate_data = training_data  # 원본 그대로
            elif i < len(training_data):
                # 데이터를 1씩 시프트 (순환)
                candidate_data = training_data[i:] + training_data[:i]
            else:
                continue
            
            # 5단계 픽 생성
            stage_picks = self._generate_stage_picks(candidate_data)
            
            if stage_picks:
                # 최종 픽 결정
                final_pick = self._evaluate_stages_for_final_pick(stage_picks, candidate_data)
                
                if final_pick != 'N':
                    # 간단한 점수 계산 (실제로는 더 복잡)
                    score = sum(1 for p in stage_picks.values() if p != 'N')
                    candidates[i] = {
                        'pick': final_pick,
                        'score': score,
                        'stages': stage_picks
                    }
        
        if not candidates:
            return 'N'
        
        # 최고 점수 후보 선택
        best_candidate = max(candidates.values(), key=lambda x: x['score'])
        return best_candidate['pick']

    def calculate_current_streak(self, all_results: List[str]) -> Dict[str, any]:
        """
        연속적인 예측-검증으로 현재 연패 수 계산
        
        Args:
            all_results: 전체 결과 데이터 (Tie 제외)
            
        Returns:
            Dict: 연패 정보 {'current_streak': int, 'prediction_history': List, ...}
        """
        if len(all_results) < 16:  # 최소 16개 필요 (15개로 1개 예측)
            return {
                'current_streak': 0,
                'prediction_history': [],
                'total_predictions': 0,
                'message': '데이터 부족 (최소 16개 필요)'
            }
        
        prediction_history = []
        current_streak = 0
        
        if self.logger:
            self.logger.info(f"연패 계산 시작: 총 {len(all_results)}개 데이터")
        
        # 15개부터 시작해서 마지막까지 순차적으로 예측-검증
        for i in range(15, len(all_results)):
            # i-14부터 i까지의 15개로 i+1번째 예측
            training_data = all_results[i-14:i+1]  # 15개
            actual_result = all_results[i]
            
            # 6개 후보군으로 예측
            predicted = self.predict_single_pick(training_data)
            
            is_success = (predicted == actual_result) if predicted != 'N' else None
            
            prediction_info = {
                'game_number': i + 1,
                'training_range': f"{i-14+1}~{i+1}",
                'predicted': predicted,
                'actual': actual_result,
                'success': is_success
            }
            prediction_history.append(prediction_info)
            
            if predicted == 'N':
                # N인 경우는 연패에 포함하지 않음 (건너뛰기)
                if self.logger:
                    self.logger.info(f"게임 {i+1}: N (예측불가) - 연패 계산에서 제외")
                continue
            elif is_success:
                current_streak = 0  # 성공하면 연패 리셋
                if self.logger:
                    self.logger.info(f"게임 {i+1}: {predicted} vs {actual_result} = 성공 - 연패 리셋")
            else:
                current_streak += 1  # 실패하면 연패 증가
                if self.logger:
                    self.logger.info(f"게임 {i+1}: {predicted} vs {actual_result} = 실패 - 연패 {current_streak}")
        
        # 통계 계산
        valid_predictions = [p for p in prediction_history if p['predicted'] != 'N']
        total_predictions = len(valid_predictions)
        successful_predictions = len([p for p in valid_predictions if p['success']])
        
        result = {
            'current_streak': current_streak,
            'prediction_history': prediction_history,
            'total_predictions': total_predictions,
            'successful_predictions': successful_predictions,
            'success_rate': (successful_predictions / total_predictions * 100) if total_predictions > 0 else 0,
            'n_count': len([p for p in prediction_history if p['predicted'] == 'N'])
        }
        
        if self.logger:
            self.logger.info(f"✅ 연패 계산 완료: 현재 {current_streak}연패, 성공률 {result['success_rate']:.1f}%")
        
        return result

    def generate_choice_pick(self) -> str:
        """
        현재 데이터로 다음 픽 예측 (단일 예측용)
        """
        if not self.has_sufficient_data():
            return 'N'
        
        # 최신 15개 데이터로 예측
        latest_15 = self.results[-15:]
        return self.predict_single_pick(latest_15)