#!/usr/bin/env python3
"""
실제 ChoicePickSystem 동작 테스트
"""

import sys
import os
sys.path.append('.')

def test_choice_pick_logic():
    """실제 ChoicePickSystem으로 테스트"""
    try:
        from utils.choice_pick import ChoicePickSystem
        print("✅ ChoicePickSystem import 성공")
    except ImportError as e:
        print(f"❌ ChoicePickSystem import 실패: {e}")
        return
    
    # 테스트 데이터 - 실제 서버로 보낸 데이터와 동일
    test_pattern = "BPBPBPBPBPBPBPBPBPBPBBBBBPPPPPBBBBBPPPPPPPPPPBBBBBPPPPPBBBBBBPBPBPBPBP"
    
    print(f"📊 테스트 패턴: {test_pattern}")
    print(f"📏 패턴 길이: {len(test_pattern)}개")
    print(f"🎯 예측 가능: {len(test_pattern) - 15}개 (16번째부터)")
    
    # 연패 카운트
    current_streak = 0
    max_streak = 0
    all_predictions = []
    
    # 16번째부터 예측 시작
    for i in range(15, len(test_pattern)):
        # 15개 데이터로 예측
        prediction_data = list(test_pattern[i-15:i])
        actual_result = test_pattern[i]
        
        # ChoicePickSystem으로 예측
        choice_system = ChoicePickSystem()
        choice_system.add_multiple_results(prediction_data)
        
        if choice_system.has_sufficient_data():
            predicted = choice_system.generate_choice_pick()
            is_win = predicted == actual_result
            
            all_predictions.append({
                "game": i + 1,
                "data": "".join(prediction_data),
                "predicted": predicted,
                "actual": actual_result,
                "result": "승" if is_win else "패"
            })
            
            # 연패 계산
            if not is_win:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
    
    # 최신 결과부터 현재 연패 계산
    final_streak = 0
    for pred in reversed(all_predictions):
        if pred["result"] == "패":
            final_streak += 1
        else:
            break
    
    print("\n🎯 예측 결과:")
    print("-" * 80)
    for pred in all_predictions[-10:]:  # 최근 10개만 표시
        print(f"게임 {pred['game']}: {pred['data']} → {pred['predicted']} vs {pred['actual']} = {pred['result']}")
    
    print("-" * 80)
    print(f"📊 총 예측: {len(all_predictions)}개")
    win_count = sum(1 for p in all_predictions if p["result"] == "승")
    print(f"📈 성공률: {win_count}/{len(all_predictions)} = {win_count/len(all_predictions)*100:.1f}%")
    print(f"🔥 현재 연패: {final_streak}회")
    print(f"📉 최대 연패: {max_streak}회")
    
    return final_streak, max_streak

def create_harder_pattern():
    """연패가 나올 수 있는 더 어려운 패턴 생성"""
    print("\n💪 더 어려운 패턴 생성...")
    
    # 초이스픽이 예측하기 어려운 패턴
    harder_pattern = (
        # 기본 15개
        "BPBPBPBPBPBPBPB" +
        # 갑작스러운 변화들 (예측하기 어려움)
        "BBBBPPPPBBBBPPPPBBBBPPPPBBBBPPPP" +
        # 완전 랜덤
        "BPBBBPPPBBBPPPBBBPPPBBBPPP" +
        # 또 다른 패턴
        "PBPBPBPBPBPBPBPBPBPB"
    )
    
    print(f"📊 어려운 패턴: {harder_pattern}")
    print(f"📏 길이: {len(harder_pattern)}개")
    
    return harder_pattern

def main():
    print("🧪 실제 ChoicePickSystem 테스트")
    print("=" * 50)
    
    # 1. 현재 패턴 테스트
    current_streak, max_streak = test_choice_pick_logic()
    
    # 2. 더 어려운 패턴 테스트  
    if max_streak < 3:
        print("\n현재 패턴에서 연패가 부족합니다. 더 어려운 패턴을 시도합니다...")
        harder_pattern = create_harder_pattern()
        
        print(f"\n🎯 어려운 패턴으로 재테스트:")
        # 하드 패턴으로 다시 테스트하는 로직을 추가할 수 있음
    
    print(f"\n✅ 테스트 완료 - 현재 연패: {current_streak}, 최대 연패: {max_streak}")

if __name__ == "__main__":
    main()