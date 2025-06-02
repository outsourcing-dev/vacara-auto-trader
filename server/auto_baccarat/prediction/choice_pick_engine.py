import logging
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

class ChoicePickEngine:
    """
    초이스 픽 5단계 예측 알고리즘 엔진
    15개 데이터를 기반으로 16번 픽을 예측하는 핵심 로직
    """
    
    def __init__(self):
        """초기화"""
        self.logger = logger
    
    def predict_16th_pick(self, results: List[str]) -> str:
        """
        15개 결과를 기반으로 16번 픽 예측
        
        Args:
            results: 15개의 게임 결과 ['P', 'B', 'P', ...]
            
        Returns:
            str: 예측된 16번 픽 ('P', 'B', 또는 'N')
        """
        if len(results) < 15:
            self.logger.warning(f"데이터 부족: {len(results)}/15개")
            return 'N'
        
        # 정확히 15개만 사용
        results = results[:15]
        
        # 5단계 계산
        stage1, stage2, stage3, stage4, stage5 = self._calculate_five_stages(results)
        
        # 최종 픽 결정 (5단계부터 역순으로 유효한 픽 선택)
        final_pick = self._select_final_pick([stage5, stage4, stage3, stage2, stage1])
        
        self.logger.debug(f"16번 픽 예측 결과: {final_pick} (1°={stage1}, 2°={stage2}, 3°={stage3}, 4°={stage4}, 5°={stage5})")
        
        return final_pick
    
    def _calculate_five_stages(self, results: List[str]) -> Tuple[str, str, str, str, str]:
        """
        5단계 알고리즘 계산
        
        Args:
            results: 15개의 게임 결과
            
        Returns:
            Tuple[str, str, str, str, str]: 5단계 픽 결과
        """
        # 16번 픽 계산 (인덱스 15)
        pick_number = 16
        pos = pick_number - 1  # 0-기반 인덱스
        
        # ========= 1단계 =========
        # pick1(12번) == pick2(13번) ? pick4(15번) : !pick4(15번)
        pick1 = self._safe_get(results, pos - 4)  # 11번째 (인덱스 11)
        pick2 = self._safe_get(results, pos - 3)  # 12번째 (인덱스 12)  
        pick4 = self._safe_get(results, pos - 1)  # 15번째 (인덱스 14)
        
        if pick1 == 'N' or pick2 == 'N' or pick4 == 'N':
            stage1 = 'N'
        else:
            stage1 = pick4 if pick1 == pick2 else self._get_opposite(pick4)
        
        # ========= 2단계 =========
        # 이전 4판의 1단계 결과와 실제 결과 비교 (승률 50% 이상이면 유지)
        if pick_number < 6:
            stage2 = 'N'
        else:
            # 12, 13, 14, 15번 픽의 1단계 결과들을 계산해야 함
            win_count = 0
            for i in range(1, 5):  # 1, 2, 3, 4
                prev_pick_num = pick_number - i  # 15, 14, 13, 12
                prev_stage1 = self._calculate_stage1_for_pick(results, prev_pick_num)
                prev_actual = self._safe_get(results, prev_pick_num - 1)  # 실제 결과
                
                if prev_stage1 != 'N' and prev_actual != 'N' and prev_stage1 == prev_actual:
                    win_count += 1
            
            stage2 = stage1 if win_count >= 2 else self._get_opposite(stage1)
        
        # ========= 3단계 =========
        if pick_number < 6:
            stage3 = 'N'
        elif 6 <= pick_number <= 8:
            stage3 = stage2
        else:
            # 15번 픽의 2단계 결과와 15번 실제 결과 비교
            prev_stage2 = self._calculate_stage2_for_pick(results, 15)
            prev_actual = self._safe_get(results, 14)  # 15번 실제 결과
            
            if prev_stage2 != 'N' and prev_actual != 'N':
                stage3 = stage2 if prev_actual == prev_stage2 else self._get_opposite(stage2)
            else:
                stage3 = stage2
        
        # ========= 4단계 =========
        if pick_number == 5:
            stage4 = 'N'
        elif 6 <= pick_number <= 10:
            stage4 = stage3
        else:
            # 15번 픽의 3단계 결과와 15번 실제 결과 비교
            prev_stage3 = self._calculate_stage3_for_pick(results, 15)
            prev_actual = self._safe_get(results, 14)  # 15번 실제 결과
            
            if prev_stage3 != 'N' and prev_actual != 'N':
                stage4 = stage3 if prev_actual == prev_stage3 else self._get_opposite(stage3)
            else:
                stage4 = stage3
        
        # ========= 5단계 =========
        if pick_number == 5:
            stage5 = 'N'
        elif 6 <= pick_number <= 11:
            stage5 = stage1
        else:
            # 이전 4판의 4단계 결과와 실제 결과 비교
            win_count = 0
            for i in range(1, 5):  # 1, 2, 3, 4
                prev_pick_num = pick_number - i  # 15, 14, 13, 12
                prev_stage4 = self._calculate_stage4_for_pick(results, prev_pick_num)
                prev_actual = self._safe_get(results, prev_pick_num - 1)  # 실제 결과
                
                if prev_stage4 != 'N' and prev_actual != 'N' and prev_stage4 == prev_actual:
                    win_count += 1
            
            stage5 = stage4 if win_count >= 2 else self._get_opposite(stage4)
        
        return stage1, stage2, stage3, stage4, stage5
    
    def _calculate_stage1_for_pick(self, results: List[str], pick_number: int) -> str:
        """특정 픽 번호의 1단계 결과 계산"""
        pos = pick_number - 1
        pick1 = self._safe_get(results, pos - 4)
        pick2 = self._safe_get(results, pos - 3)
        pick4 = self._safe_get(results, pos - 1)
        
        if pick1 == 'N' or pick2 == 'N' or pick4 == 'N':
            return 'N'
        
        return pick4 if pick1 == pick2 else self._get_opposite(pick4)
    
    def _calculate_stage2_for_pick(self, results: List[str], pick_number: int) -> str:
        """특정 픽 번호의 2단계 결과 계산"""
        if pick_number < 6:
            return 'N'
        
        stage1 = self._calculate_stage1_for_pick(results, pick_number)
        if stage1 == 'N':
            return 'N'
        
        # 이전 4판의 1단계 승률 계산
        win_count = 0
        for i in range(1, 5):
            prev_pick_num = pick_number - i
            if prev_pick_num < 5:
                continue
            prev_stage1 = self._calculate_stage1_for_pick(results, prev_pick_num)
            prev_actual = self._safe_get(results, prev_pick_num - 1)
            
            if prev_stage1 != 'N' and prev_actual != 'N' and prev_stage1 == prev_actual:
                win_count += 1
        
        return stage1 if win_count >= 2 else self._get_opposite(stage1)
    
    def _calculate_stage3_for_pick(self, results: List[str], pick_number: int) -> str:
        """특정 픽 번호의 3단계 결과 계산"""
        if pick_number < 6:
            return 'N'
        elif 6 <= pick_number <= 8:
            return self._calculate_stage2_for_pick(results, pick_number)
        else:
            stage2 = self._calculate_stage2_for_pick(results, pick_number)
            if stage2 == 'N':
                return 'N'
            
            # 이전 픽의 2단계 결과와 실제 결과 비교
            prev_stage2 = self._calculate_stage2_for_pick(results, pick_number - 1)
            prev_actual = self._safe_get(results, pick_number - 2)
            
            if prev_stage2 != 'N' and prev_actual != 'N':
                return stage2 if prev_actual == prev_stage2 else self._get_opposite(stage2)
            else:
                return stage2
    
    def _calculate_stage4_for_pick(self, results: List[str], pick_number: int) -> str:
        """특정 픽 번호의 4단계 결과 계산"""
        if pick_number == 5:
            return 'N'
        elif 6 <= pick_number <= 10:
            return self._calculate_stage3_for_pick(results, pick_number)
        else:
            stage3 = self._calculate_stage3_for_pick(results, pick_number)
            if stage3 == 'N':
                return 'N'
            
            # 이전 픽의 3단계 결과와 실제 결과 비교
            prev_stage3 = self._calculate_stage3_for_pick(results, pick_number - 1)
            prev_actual = self._safe_get(results, pick_number - 2)
            
            if prev_stage3 != 'N' and prev_actual != 'N':
                return stage3 if prev_actual == prev_stage3 else self._get_opposite(stage3)
            else:
                return stage3
    
    def _safe_get(self, lst: List[str], idx: int, default: str = 'N') -> str:
        """안전하게 리스트에서 값 가져오기"""
        return lst[idx] if 0 <= idx < len(lst) else default
    
    def _get_opposite(self, pick: str) -> str:
        """반대 픽 반환"""
        if pick == 'P':
            return 'B'
        elif pick == 'B':
            return 'P'
        else:
            return 'N'
    
    def _select_final_pick(self, stages: List[str]) -> str:
        """5단계 중 유효한 첫 번째 픽 선택"""
        for stage in stages:
            if stage in ['P', 'B']:
                return stage
        return 'N'