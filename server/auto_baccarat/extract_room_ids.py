import subprocess
import json
import os
import time
import sys
import re
from datetime import datetime

def print_header():
    print("="*54)
    print("     바카라 방 ID 추출 도구     ".center(54))
    print("="*54)
    print("이 스크립트는 WebSocket 통신에서 모든 방 ID를 추출하여")
    print("room_ids.txt 파일로 저장합니다.")
    print("")
    print("3분 동안 데이터를 수집한 후 자동 종료됩니다.")
    print("="*54)
    print("")

def run_program_with_timeout(timeout=180):  # 3분(180초)
    """지정된 시간 동안 프로그램 실행 후 종료"""
    print(f"WebSocket 연결 시작 - {timeout}초 동안 데이터 수집...")
    
    # 로그 파일 열기
    log_file = open("room_id_extraction.log", "w", encoding="utf-8")
    
    try:
        # 디버그 모드로 프로그램 실행
        process = subprocess.Popen(
            ["python", "main.py", "--debug", "--filter-off"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1  # 라인 버퍼링
        )
        
        # 결과 저장을 위한 세트 (중복 제거)
        room_ids = set()
        
        # 진행률 표시
        start_time = time.time()
        last_progress = 0
        
        print("수집 중: ", end="", flush=True)
        
        # 지정된 시간만큼 실행하며 출력 파싱
        while process.poll() is None and (time.time() - start_time < timeout):
            # 출력 라인 읽기
            output = process.stdout.readline()
            if output:
                # 로그 파일에 기록
                log_file.write(output)
                log_file.flush()
                
                # 방 ID 추출 패턴
                # 1. lobby.historyUpdated 메시지에서 추출
                if "방 ID:" in output:
                    match = re.search(r'방 ID: ([^\s:(]+)', output)
                    if match:
                        room_id = match.group(1)
                        room_ids.add(room_id)
                
                # 2. 다른 형태의 ID 패턴 추출 (콜론이 포함된 ID)
                colon_matches = re.findall(r'([a-zA-Z0-9]+):[a-zA-Z0-9]+', output)
                for match in colon_matches:
                    if len(match) > 5:  # 너무 짧은 ID는 제외
                        room_ids.add(match)
                
                # 3. 직접적인 ID 패턴 (숫자와 알파벳으로 구성된 긴 문자열)
                id_matches = re.findall(r'"([a-zA-Z0-9]{10,})"', output)
                for match in id_matches:
                    room_ids.add(match)
            
            # 진행률 업데이트 (10%마다)
            elapsed = time.time() - start_time
            progress = int((elapsed / timeout) * 10)
            if progress > last_progress:
                print("■", end="", flush=True)
                last_progress = progress
        
        # 프로세스 종료
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            print(f"\n프로그램 실행 종료됨 - {len(room_ids)}개의 고유 방 ID 추출")
        
        return room_ids
        
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단됨")
        if process.poll() is None:
            process.terminate()
        return room_ids
    finally:
        log_file.close()

def save_room_ids(room_ids):
    """추출된 방 ID를 파일로 저장"""
    # 날짜, 시간을 포함한 파일명
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"room_ids_{timestamp}.txt"
    
    with open(filename, "w", encoding="utf-8") as f:
        # 알파벳 순으로 정렬하여 저장
        for room_id in sorted(room_ids):
            f.write(f"{room_id}\n")
    
    # 최신 버전의 파일도 따로 저장
    with open("room_ids_latest.txt", "w", encoding="utf-8") as f:
        for room_id in sorted(room_ids):
            f.write(f"{room_id}\n")
    
    return filename, len(room_ids)

def analyze_results(filename, count):
    """추출 결과 분석"""
    print("\n" + "="*54)
    print("방 ID 추출 결과".center(54))
    print("="*54)
    
    print(f"총 {count}개의 고유 방 ID를 추출했습니다.")
    print(f"결과가 {filename} 파일에 저장되었습니다.")
    
    # 기존 매핑 파일과 비교
    if os.path.exists("room_mappings.json"):
        try:
            with open("room_mappings.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            
            existing_ids = set(data.get("room_mappings", {}).keys())
            
            # 새로 추출된 ID 중 기존 매핑에 없는 ID 확인
            with open(filename, "r", encoding="utf-8") as f:
                extracted_ids = set(line.strip() for line in f)
            
            new_ids = extracted_ids - existing_ids
            
            if new_ids:
                print(f"\n기존 매핑에 없는 {len(new_ids)}개의 새 ID를 발견했습니다:")
                for i, new_id in enumerate(sorted(new_ids)[:10], 1):  # 최대 10개만 표시
                    print(f"  {i}. {new_id}")
                
                if len(new_ids) > 10:
                    print(f"  ... 외 {len(new_ids) - 10}개")
                
                # 새 ID를 템플릿 파일로 저장
                template_filename = "new_room_ids_template.json"
                template = {"room_mappings": {}}
                
                for new_id in sorted(new_ids):
                    template["room_mappings"][new_id] = ""  # 빈 이름으로 설정
                
                with open(template_filename, "w", encoding="utf-8") as f:
                    json.dump(template, f, indent=4, ensure_ascii=False)
                
                print(f"\n새 ID가 {template_filename} 파일에 템플릿 형식으로 저장되었습니다.")
                print("이 파일에 방 이름을 추가한 후 기존 room_mappings.json과 병합하세요.")
            else:
                print("\n모든 추출된 ID가 이미 room_mappings.json에 존재합니다.")
            
        except Exception as e:
            print(f"\n매핑 파일 분석 중 오류 발생: {e}")
    else:
        print("\nroom_mappings.json 파일이 존재하지 않습니다.")
        print("추출된 ID를 사용하여 새 매핑 파일을 만드세요.")
    
    print("="*54)

def main():
    print_header()
    room_ids = run_program_with_timeout(180)  # 3분
    if room_ids:
        filename, count = save_room_ids(room_ids)
        analyze_results(filename, count)

if __name__ == "__main__":
    main()