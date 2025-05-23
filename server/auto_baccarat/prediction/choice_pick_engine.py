import logging
from typing import Optional, List
from utils.choice_pick import ChoicePickSystem


class ChoicePickEngine:
    """
    ChoicePick 기반 예측 엔진
    - 최신 15개 결과를 기반으로 6개 후보 중 최적의 픽을 선정
    - 16번째 결과 예측 수행
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        # 내부 ChoicePickSystem 사용
        self.system = ChoicePickSystem(logger=self.logger)

    def reset(self) -> None:
        """시스템 초기화"""
        self.system.clear()

    def add_result(self, result: str) -> None:
        """결과 추가 (예: 'P', 'B')"""
        self.system.add_result(result)

    def add_results(self, results: List[str]) -> None:
        """다수 결과 추가"""
        self.system.add_multiple_results(results)

    def has_enough_data(self) -> bool:
        """예측 가능한 최소 데이터 확보 여부"""
        return self.system.has_sufficient_data()

    def predict(self) -> str:
        """
        다음 픽 예측
        - 후보 생성 및 고정 후보 기반 예측
        - 예측 불가 시 'N' 반환
        """
        pick = self.system.generate_choice_pick()
        if pick == 'N':
            self.logger.info("예측 불가 (N 반환)")
            return 'N'

        # get_reverse_bet_pick 호출
        final_bet = self.system.get_reverse_bet_pick(pick)
        self.logger.info(f"예측 픽: {pick} → 최종 베팅 방향 반영: {final_bet}")
        return final_bet

    def record_result(self, is_win: bool) -> None:
        """예측 결과 기록"""
        self.system.record_betting_result(is_win)

    def should_change_room(self) -> bool:
        """방 이동 여부 판단"""
        return self.system.should_change_room()

    def reset_after_room_change(self) -> None:
        """방 이동 후 초기화"""
        self.system.reset_after_room_change()

    def get_current_bet_amount(self, widget_position: Optional[int] = None) -> int:
        """현재 베팅 금액 반환"""
        return self.system.get_current_bet_amount(widget_position)
