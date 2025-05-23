import logging
from typing import List, Dict, Optional


class ChoicePickSystem:
    """
    초이스 픽 시스템 - 15판 기준 예측 로직만 구현
    """
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.results: List[str] = []  # 최근 15판 결과 (P/B만)
        self.stage1_picks: List[str] = []
        self.stage2_picks: List[str] = []
        self.stage3_picks: List[str] = []
        self.stage4_picks: List[str] = []
        self.stage5_picks: List[str] = []

    def add_result(self, result: str) -> None:
        if result in ('P', 'B'):
            self.results.append(result)
            if len(self.results) > 15:
                self.results = self.results[-15:]

    def add_multiple_results(self, results: List[str]) -> None:
        filtered = [r for r in results if r in ('P', 'B')]
        self.results.extend(filtered)
        if len(self.results) > 15:
            self.results = self.results[-15:]

    def has_sufficient_data(self) -> bool:
        return len(self.results) >= 15

    def get_opposite_pick(self, pick: str) -> str:
        return 'B' if pick == 'P' else 'P'

    def get_reverse_bet_pick(self, pick: str) -> str:
        """픽의 반대값 반환"""
        if pick == 'P':
            return 'B'
        elif pick == 'B':
            return 'P'
        return 'N'

    def _generate_all_stage_picks(self, results: List[str]) -> Dict[int, str]:
        def safe_get(lst, idx):
            return lst[idx] if 0 <= idx < len(lst) else 'N'

        all_picks = {}
        self.stage1_picks.clear()
        self.stage2_picks.clear()
        self.stage3_picks.clear()
        self.stage4_picks.clear()
        self.stage5_picks.clear()

        for pick_number in range(5, len(results) + 2):
            pos = pick_number - 1

            pick1 = safe_get(results, pos - 4)
            pick2 = safe_get(results, pos - 3)
            pick4 = safe_get(results, pos - 1)

            stage1 = pick4 if pick1 == pick2 else self.get_opposite_pick(pick4) if pick1 != 'N' and pick2 != 'N' and pick4 != 'N' else 'N'
            self.stage1_picks.append(stage1)

            if pick_number < 6:
                stage2 = 'N'
            else:
                win_count = 0
                for i in range(1, 5):
                    prev_idx = pick_number - i - 1
                    if 0 <= prev_idx < len(self.stage1_picks):
                        if self.stage1_picks[prev_idx] == safe_get(results, prev_idx):
                            win_count += 1
                stage2 = stage1 if win_count >= 2 else self.get_opposite_pick(stage1)
            self.stage2_picks.append(stage2)

            if pick_number < 6:
                stage3 = 'N'
            elif pick_number <= 8:
                stage3 = stage2
            else:
                prev_idx = pick_number - 2
                prev_result = safe_get(results, prev_idx)
                prev_stage2 = safe_get(self.stage2_picks, prev_idx)
                stage3 = stage2 if prev_result == prev_stage2 else self.get_opposite_pick(stage2)
            self.stage3_picks.append(stage3)

            if pick_number == 5:
                stage4 = 'N'
            elif pick_number <= 10:
                stage4 = stage3
            else:
                prev_idx = pick_number - 2
                prev_result = safe_get(results, prev_idx)
                prev_stage3 = safe_get(self.stage3_picks, prev_idx)
                stage4 = stage3 if prev_result == prev_stage3 else self.get_opposite_pick(stage3)
            self.stage4_picks.append(stage4)

            if pick_number == 5:
                stage5 = 'N'
            elif pick_number <= 11:
                stage5 = stage1
            else:
                win_count = 0
                for i in range(1, 5):
                    idx = pick_number - i - 1
                    if 0 <= idx < len(self.stage4_picks):
                        if self.stage4_picks[idx] == safe_get(results, idx):
                            win_count += 1
                stage5 = stage4 if win_count >= 2 else self.get_opposite_pick(stage4)
            self.stage5_picks.append(stage5)

            final_pick = next((p for p in [stage5, stage4, stage3, stage2, stage1] if p != 'N'), 'N')
            all_picks[pick_number] = final_pick

        return all_picks

    def generate_choice_pick(self) -> str:
        if not self.has_sufficient_data():
            return 'N'

        picks = self._generate_all_stage_picks(self.results)
        next_pick_num = len(self.results) + 1
        return picks.get(next_pick_num, 'N')
