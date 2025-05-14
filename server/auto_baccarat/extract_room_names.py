import subprocess
import json
import os
import time
import sys

def print_header():
    print("="*54)
    print("     바카라 방 이름 추출 도구     ".center(54))
    print("="*54)
    print("이 스크립트는 WebSocket 통신에서 방 이름과 ID를 추출하여")
    print("room_mappings_discovered.json 파일로 저장합니다.")
    print("")
    print("초기 연결 시 모든 메시지를 분석하고 30초 후 자동 종료됩니다.")
    print("="*54)
    print("")

def run_program_with_timeout(timeout=30):
    """지정된 시간 동안 프로그램 실행 후 종료"""
    print(f"WebSocket 연결 시작 - {timeout}초 동안 데이터 수집...")
    
    # 로그 파일 열기
    log_file = open("table_extraction.log", "w", encoding="utf-8")
    
    try:
        # 디버그 모드로 프로그램 실행
        process = subprocess.Popen(
            ["python", "main.py", "--debug", "--filter-off"],
            stdout=log_file,
            stderr=log_file,
            text=True
        )
        
        # 지정된 시간만큼 실행
        start_time = time.time()
        while process.poll() is None and (time.time() - start_time < timeout):
            sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(1)
        
        # 프로세스 종료
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            print("\n프로그램 실행 종료됨")
        
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단됨")
        if process.poll() is None:
            process.terminate()
    finally:
        log_file.close()

def analyze_results():
    """추출 결과 분석"""
    print("\n" + "="*54)
    print("방 이름 추출 결과".center(54))
    print("="*54)
    
    if os.path.exists("room_mappings_discovered.json"):
        print("🎉 성공적으로 방 이름 매핑 정보를 추출했습니다!")
        print("")
        
        try:
            with open("room_mappings_discovered.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            
            room_mappings = data.get("room_mappings", {})
            
            # 매핑 개수
            print(f"총 {len(room_mappings)}개의 방 정보가 추출되었습니다.")
            
            # 처음 5개 매핑 출력
            print("\n추출된 방 정보 샘플 (5개):")
            for i, (room_id, name) in enumerate(list(room_mappings.items())[:5]):
                print(f"  {room_id}: {name}")
            
            # Speed 관련 방 검색
            speed_rooms = {}
            for room_id, name in room_mappings.items():
                if "speed" in name.lower() or "스피드" in name:
                    speed_rooms[room_id] = name
            
            print(f"\nSpeed 관련 방 목록 ({len(speed_rooms)}개):")
            for i, (room_id, name) in enumerate(list(speed_rooms.items())[:10]):  # 처음 10개만
                print(f"  {room_id}: {name}")
            
            if len(speed_rooms) > 10:
                print(f"  ... 외 {len(speed_rooms) - 10}개")
            
            # 파일 복사 안내
            print("\nroom_mappings_discovered.json 파일을 room_mappings.json으로 복사하면")
            print("필터링된 결과를 확인할 수 있습니다.")
            print("")
            print("명령어: copy room_mappings_discovered.json room_mappings.json")
            
        except Exception as e:
            print(f"파일 분석 중 오류 발생: {e}")
    else:
        print("❌ 방 이름 매핑 정보 추출에 실패했습니다.")
        print("로그 파일 table_extraction.log를 확인하세요.")
    
    print("="*54)

def main():
    print_header()
    run_program_with_timeout(30)
    analyze_results()

if __name__ == "__main__":
    main()