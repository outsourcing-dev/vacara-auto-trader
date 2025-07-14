#!/usr/bin/env python3
"""
연패 계산 디버깅 테스트
"""

import requests
import json

class DebugStreakTester:
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
    
    def send_debug_data(self):
        """디버깅용 더 많은 데이터 전송"""
        print("📡 디버깅용 테스트 데이터 전송...")
        
        # 더 많은 데이터 (70개) - 연패가 확실히 나오도록
        test_data = {
            "room_id": "BonsaiBacc000001",
            "mapped_room_name": "본자이 스피드 바카라 A (디버그)",
            "all_results": [
                # 처음 20개: 랜덤한 기본 데이터
                "R","B","R","B","R","B","R","B","R","B",
                "R","B","R","B","R","B","R","B","R","B",
                
                # 21~40: 패턴 생성
                "R","R","R","R","R","B","B","B","B","B",
                "R","R","R","R","R","B","B","B","B","B",
                
                # 41~60: 예측이 틀리도록 의도적 패턴
                "B","B","B","B","B","R","R","R","R","R",
                "B","B","B","B","B","R","R","R","R","R",
                
                # 61~70: 마지막에 연패 유도
                "R","B","R","B","R","B","R","B","R","B"
            ],
            "total_results": 70,
            "latest_result": "B"
        }
        
        print(f"📊 전송 데이터: {len(test_data['all_results'])}개")
        print(f"🎲 원본 패턴: {''.join(test_data['all_results'])}")
        
        # R/B를 P/B로 변환해서 확인
        converted = []
        for r in test_data['all_results']:
            if r == "R":  # Banker
                converted.append("B")
            elif r == "B":  # Player
                converted.append("P")
        
        print(f"🔄 변환 패턴: {''.join(converted)}")
        print(f"📈 예측 가능 개수: {len(converted) - 15}개 (16번째부터 {len(converted)}번째까지)")
        
        try:
            response = requests.post(
                f"{self.base_url}/api/rooms/results",
                json=test_data
            )
            data = response.json()
            
            if data["status"] == "success":
                print(f"✅ 데이터 전송 성공: {data['room_name']}")
                print(f"🔥 현재 연패: {data.get('current_streak', 0)}회")
                return True
            else:
                print(f"❌ 전송 실패: {data.get('message', '알 수 없는 오류')}")
                return False
                
        except Exception as e:
            print(f"❌ 데이터 전송 오류: {e}")
            return False
    
    def debug_choice_pick_manually(self):
        """초이스픽 수동 디버깅"""
        print("\n🔍 초이스픽 수동 디버깅...")
        
        # 간단한 테스트 패턴
        test_pattern = "BPBPBPBPBPBPBPBPBPBPBPBPBPBPBPBPBPBPBPBP"  # 40개
        print(f"테스트 패턴: {test_pattern}")
        print(f"패턴 길이: {len(test_pattern)}개")
        print(f"예측 가능: {len(test_pattern) - 15}개")
        
        # 수동으로 몇 개 예측 시뮬레이션
        for i in range(15, min(25, len(test_pattern))):  # 처음 10개만
            prediction_data = test_pattern[i-15:i]
            actual = test_pattern[i]
            
            # 초이스픽 로직 간단 시뮬레이션 (실제로는 복잡)
            # 여기서는 단순히 마지막 결과의 반대로 예측한다고 가정
            last_result = prediction_data[-1]
            predicted = "P" if last_result == "B" else "B"
            
            is_win = predicted == actual
            result = "승" if is_win else "패"
            
            print(f"게임 {i+1}: {prediction_data} → 예측:{predicted} 실제:{actual} = {result}")
    
    def check_room_details(self, room_id: str = "BonsaiBacc000001"):
        """방 상세 정보 확인"""
        print(f"\n🔍 방 상세 정보: {room_id}")
        
        # 서버에 저장된 실제 데이터 확인
        try:
            # 내부 API가 있다면 사용, 없다면 기본 연패 조회
            response = requests.get(f"{self.base_url}/api/rooms/streak/{room_id}")
            data = response.json()
            
            print(f"응답 상태: {data['status']}")
            print(f"응답 데이터: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
        except Exception as e:
            print(f"❌ 상세 조회 오류: {e}")
    
    def run_debug_test(self):
        """디버깅 테스트 실행"""
        print("🐛 연패 계산 디버깅 테스트")
        print("="*50)
        
        # 1. 초이스픽 수동 시뮬레이션
        self.debug_choice_pick_manually()
        
        # 2. 디버깅 데이터 전송
        if self.send_debug_data():
            # 3. 방 상세 정보 확인
            self.check_room_details()
            
            # 4. 다시 연패 조회
            print("\n🎯 연패 재조회...")
            try:
                response = requests.get(f"{self.base_url}/api/rooms/streak/BonsaiBacc000001")
                data = response.json()
                
                if data["status"] == "success":
                    print(f"✅ {data['room_name']}: {data['current_streak']}연패")
                else:
                    print(f"❌ 조회 실패: {data.get('message')}")
                    
            except Exception as e:
                print(f"❌ 재조회 오류: {e}")

def main():
    """디버깅 메인"""
    tester = DebugStreakTester()
    
    print("🐛 연패 디버깅 도구")
    print("="*30)
    
    while True:
        print("\n📋 디버깅 메뉴:")
        print("1. 초이스픽 수동 시뮬레이션")
        print("2. 디버깅 데이터 전송")
        print("3. 방 상세 정보 확인")
        print("4. 전체 디버깅 실행")
        print("5. 종료")
        
        choice = input("\n선택하세요 (1-5): ").strip()
        
        if choice == "1":
            tester.debug_choice_pick_manually()
        elif choice == "2":
            tester.send_debug_data()
        elif choice == "3":
            tester.check_room_details()
        elif choice == "4":
            tester.run_debug_test()
        elif choice == "5":
            print("👋 디버깅을 종료합니다.")
            break
        else:
            print("❌ 잘못된 선택입니다.")

if __name__ == "__main__":
    main()