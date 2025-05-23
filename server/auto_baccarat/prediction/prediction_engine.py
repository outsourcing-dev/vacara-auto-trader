import logging
from typing import List, Dict


class PredictionEngine:
    """
    기존 클라이언트 측 5단계 예측 알고리즘을 서버에서 실행하는 PredictionEngine
    """
    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.results: List[str] = []

    def add_results(self, results: List[str]) -> None:
        filtered = [r for r in results if r in ('P', 'B')]
        self.results = filtered[-15:]

    def has_sufficient_data(self) -> bool:
        return len(self.results) == 15

    def get_opposite_pick(self, pick: str) -> str:
        return 'B' if pick == 'P' else 'P'

    def _generate_all_stage_picks(self, results: List[str]) -> Dict[int, str]:
        def safe_get(lst, idx):
            return lst[idx] if 0 <= idx < len(lst) else 'N'

        stage1_picks, stage2_picks, stage3_picks, stage4_picks, stage5_picks = [], [], [], [], []
        all_picks = {}

        for pick_number in range(5, len(results) + 2):
            pos = pick_number - 1

            pick1 = safe_get(results, pos - 4)
            pick2 = safe_get(results, pos - 3)
            pick4 = safe_get(results, pos - 1)
            stage1 = pick4 if pick1 == pick2 else self.get_opposite_pick(pick4) if pick1 != 'N' and pick2 != 'N' and pick4 != 'N' else 'N'
            stage1_picks.append(stage1)

            if pick_number < 6:
                stage2 = 'N'
            else:
                win_count = sum(
                    1 for i in range(1, 5)
                    if 0 <= pick_number - i - 1 < len(stage1_picks) and
                    stage1_picks[pick_number - i - 1] == safe_get(results, pick_number - i - 1)
                )
                stage2 = stage1 if win_count >= 2 else self.get_opposite_pick(stage1)
            stage2_picks.append(stage2)

            if pick_number < 6:
                stage3 = 'N'
            elif pick_number <= 8:
                stage3 = stage2
            else:
                prev_idx = pick_number - 2
                prev_result = safe_get(results, prev_idx)
                prev_stage2 = safe_get(stage2_picks, prev_idx)
                stage3 = stage2 if prev_result == prev_stage2 else self.get_opposite_pick(stage2)
            stage3_picks.append(stage3)

            if pick_number == 5:
                stage4 = 'N'
            elif pick_number <= 10:
                stage4 = stage3
            else:
                prev_idx = pick_number - 2
                prev_result = safe_get(results, prev_idx)
                prev_stage3 = safe_get(stage3_picks, prev_idx)
                stage4 = stage3 if prev_result == prev_stage3 else self.get_opposite_pick(stage3)
            stage4_picks.append(stage4)

            if pick_number == 5:
                stage5 = 'N'
            elif pick_number <= 11:
                stage5 = stage1
            else:
                win_count = sum(
                    1 for i in range(1, 5)
                    if 0 <= pick_number - i - 1 < len(stage4_picks) and
                    stage4_picks[pick_number - i - 1] == safe_get(results, pick_number - i - 1)
                )
                stage5 = stage4 if win_count >= 2 else self.get_opposite_pick(stage4)
            stage5_picks.append(stage5)

            final_pick = next((p for p in [stage5, stage4, stage3, stage2, stage1] if p != 'N'), 'N')
            all_picks[pick_number] = final_pick

        return all_picks

    def predict(self) -> str:
        if not self.has_sufficient_data():
            return 'N'
        picks = self._generate_all_stage_picks(self.results)
        return picks.get(16, 'N')
