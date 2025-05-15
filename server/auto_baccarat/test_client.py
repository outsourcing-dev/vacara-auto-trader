import asyncio
import websockets
import json
import requests
import time
import sys
from datetime import datetime
import argparse
from urllib.parse import urlparse, parse_qs

# 서버 URL 설정 (기본값)
BASE_URL = "http://localhost:8080"
WS_URL = "ws://localhost:8080/ws/baccarat"

def extract_baccarat_config(ws_url):
    """WebSocket URL에서 바카라 설정 정보 추출"""
    try:
        # URL 파싱
        parsed_url = urlparse(ws_url)
        query_params = parse_qs(parsed_url.query)
        
        # 경로에서 bare_session_id 추출
        path_parts = parsed_url.path.split('/')
        bare_session_id = path_parts[-1]
        
        # 쿼리 파라미터에서 값 추출
        session_id = query_params.get('EVOSESSIONID', [''])[0]
        
        # instance 파라미터 처리 (하이픈으로 분리된 첫 부분만 사용)
        instance_param = query_params.get('instance', [''])[0]
        instance = instance_param.split('-')[0] if instance_param else ''
        
        client_version = query_params.get('client_version', [''])[0]
        
        # 필수 값 확인
        if not all([bare_session_id, session_id, instance, client_version]):
            print("URL에서 필수 설정값을 추출할 수 없습니다.")
            print(f"bare_session_id: {bare_session_id}")
            print(f"session_id: {session_id}")
            print(f"instance: {instance}")
            print(f"client_version: {client_version}")
            return None
        
        return {
            "session_id": session_id,
            "bare_session_id": bare_session_id,
            "instance": instance,
            "client_version": client_version
        }
    except Exception as e:
        print(f"URL 파싱 오류: {e}")
        return None

async def test_baccarat_api(user_id, ws_url=None, monitoring_time=60):
    print("=== 바카라 API 테스트 시작 ===")
    
    # 1. 세션 설정
    print("\n1. 세션 설정")
    
    if ws_url:
        # URL에서 설정 추출
        config = extract_baccarat_config(ws_url)
        if not config:
            print("유효하지 않은 URL입니다. 기본값을 사용합니다.")
            config = {
                "session_id": "s2rqzokhx5pxl6z6s3gwwsr2ynjfu62m029164bfe2f358b6214e0765d7ab5fa955eaae2fea107d75",
                "bare_session_id": "s2rqzokhx5pxl6z6",
                "instance": "7lwa0y",
                "client_version": "6.20250512.70248.51685-c40cdf22de",
                "user_id": user_id
            }
    else:
        # 기본값 사용
        print("기본값 사용")
        config = {
            "session_id": "s2rqzokhx5pxl6z6s3gwwsr2ynjfu62m029164bfe2f358b6214e0765d7ab5fa955eaae2fea107d75",
            "bare_session_id": "s2rqzokhx5pxl6z6",
            "instance": "7lwa0y",
            "client_version": "6.20250512.70248.51685-c40cdf22de",
            "user_id": user_id
        }
    
    print("\n추출된 설정 정보:")
    for key, value in config.items():
        print(f"  {key}: {value}")
    
    # 연속 횟수 설정
    print("\n2. 연패 설정")
    try:
        player_streak = int(input("플레이어 연패 감지 횟수 (기본값 3): ") or "3")
        banker_streak = int(input("뱅커 연패 감지 횟수 (기본값 3): ") or "3")
        min_results = int(input("최소 결과 수 (기본값 10): ") or "10")
    except ValueError:
        print("유효하지 않은 입력입니다. 기본값을 사용합니다.")
        player_streak = 3
        banker_streak = 3
        min_results = 10
    
    # 설정 전송
    response = requests.post(f"{BASE_URL}/api/baccarat/config", json=config)
    print_response(response)
    
    # 연패 설정 전송
    streak_settings = {
        "player_streak": player_streak,
        "banker_streak": banker_streak,
        "min_results": min_results,
        "user_id": user_id
    }
    
    response = requests.post(f"{BASE_URL}/api/baccarat/streak-settings", json=streak_settings)
    print_response(response)
    
    # 3. WebSocket 연결 준비
    print("\n3. WebSocket 연결 시작")
    websocket_task = asyncio.create_task(websocket_client(user_id))
    
    # 4. 바카라 클라이언트 시작
    print("\n4. 바카라 클라이언트 시작")
    response = requests.post(f"{BASE_URL}/api/baccarat/start/{user_id}")
    print_response(response)
    
    # 5. 모니터링 (데이터 수집)
    print(f"\n5. {monitoring_time}초간 데이터 수집 중...")
    
    # 진행 표시
    for i in range(monitoring_time):
        if i % 10 == 0:
            # 10초마다 현재 데이터 조회
            response = requests.get(f"{BASE_URL}/api/baccarat/data/{user_id}")
            print(f"\n현재 데이터 ({datetime.now().strftime('%H:%M:%S')}):")
            data = response.json()
            if "streak_data" in data.get("monitor_data", {}):
                streak_data = data["monitor_data"]["streak_data"]
                print(f"  플레이어 연패 방: {len(streak_data.get('player_streak_rooms', []))}개")
                print(f"  뱅커 연패 방: {len(streak_data.get('banker_streak_rooms', []))}개")
                
                # 연패 방이 있으면 상세 정보 출력
                player_rooms = streak_data.get('player_streak_rooms', [])
                if player_rooms:
                    print(f"  [플레이어 연패 방]")
                    for idx, room in enumerate(player_rooms[:3], 1):  # 최대 3개만 표시
                        print(f"    {idx}. {room['room_name']} - {room['streak']}연속")
                    if len(player_rooms) > 3:
                        print(f"    ... 외 {len(player_rooms) - 3}개")
                
                banker_rooms = streak_data.get('banker_streak_rooms', [])
                if banker_rooms:
                    print(f"  [뱅커 연패 방]")
                    for idx, room in enumerate(banker_rooms[:3], 1):  # 최대 3개만 표시
                        print(f"    {idx}. {room['room_name']} - {room['streak']}연속")
                    if len(banker_rooms) > 3:
                        print(f"    ... 외 {len(banker_rooms) - 3}개")
        
        print(".", end="", flush=True)
        await asyncio.sleep(1)
    
    # 6. 바카라 클라이언트 중지
    print("\n\n6. 바카라 클라이언트 중지")
    response = requests.post(f"{BASE_URL}/api/baccarat/stop/{user_id}")
    print_response(response)
    
    # 7. 최종 데이터 조회
    print("\n7. 최종 데이터 조회")
    response = requests.get(f"{BASE_URL}/api/baccarat/data/{user_id}")
    print_response(response, show_data=True)
    
    # WebSocket 태스크 종료
    websocket_task.cancel()
    try:
        await websocket_task
    except asyncio.CancelledError:
        pass
    
    print("\n=== 바카라 API 테스트 완료 ===")

async def websocket_client(user_id):
    """WebSocket 클라이언트"""
    try:
        async with websockets.connect(f"{WS_URL}/{user_id}") as websocket:
            print(f"WebSocket 연결 성공: {WS_URL}/{user_id}")
            
            # 메시지 수신 루프
            while True:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    msg_type = data.get("type", "")
                    
                    # 데이터 업데이트 메시지 처리
                    if msg_type == "data_update" and "streak_data" in data:
                        streak_data = data["streak_data"]
                        player_count = len(streak_data.get("player_streak_rooms", []))
                        banker_count = len(streak_data.get("banker_streak_rooms", []))
                        
                        if player_count > 0 or banker_count > 0:
                            print(f"\n📊 WebSocket 업데이트: P:{player_count}, B:{banker_count} 방 감지")
                            
                            # 예시로 첫 번째 연패 방 정보 출력
                            if player_count > 0:
                                room = streak_data["player_streak_rooms"][0]
                                print(f"  🔵 플레이어 연패 방: {room['room_name']} ({room['streak']}연속)")
                            
                            if banker_count > 0:
                                room = streak_data["banker_streak_rooms"][0]
                                print(f"  🔴 뱅커 연패 방: {room['room_name']} ({room['streak']}연속)")
                    
                    # 상태 업데이트 메시지 처리
                    elif msg_type == "status_update":
                        is_running = data.get("is_running", False)
                        print(f"\n🔄 WebSocket 상태 업데이트: {'✅ 실행 중' if is_running else '⛔ 중지됨'}")
                    
                    # 초기 데이터 처리
                    elif msg_type == "init_data":
                        monitor_data = data.get("monitor_data", {})
                        streak_data = monitor_data.get("streak_data", {})
                        player_count = len(streak_data.get("player_streak_rooms", []))
                        banker_count = len(streak_data.get("banker_streak_rooms", []))
                        print(f"\n📋 초기 데이터 수신: P:{player_count}, B:{banker_count} 방 감지")
                    
                except Exception as e:
                    print(f"WebSocket 메시지 처리 오류: {e}")
                    break
    
    except asyncio.CancelledError:
        print("WebSocket 연결 종료")
        raise
    except Exception as e:
        print(f"WebSocket 연결 오류: {e}")

def print_response(response, show_data=False):
    """API 응답 출력"""
    print(f"상태 코드: {response.status_code}")
    
    try:
        data = response.json()
        if "status" in data:
            print(f"상태: {data['status']}")
        if "message" in data:
            print(f"메시지: {data['message']}")
        
        if show_data and "monitor_data" in data:
            monitor_data = data["monitor_data"]
            streak_data = monitor_data.get("streak_data", {})
            print("\n연패 데이터:")
            
            # 플레이어 연패 방
            player_rooms = streak_data.get("player_streak_rooms", [])
            if player_rooms:
                print(f"\n🔵 플레이어 연패 방 ({len(player_rooms)}개):")
                for i, room in enumerate(player_rooms, 1):
                    print(f"  {i}. {room['room_name']} - {room['streak']}연속")
            else:
                print("\n🔵 플레이어 연패 방: 없음")
            
            # 뱅커 연패 방
            banker_rooms = streak_data.get("banker_streak_rooms", [])
            if banker_rooms:
                print(f"\n🔴 뱅커 연패 방 ({len(banker_rooms)}개):")
                for i, room in enumerate(banker_rooms, 1):
                    print(f"  {i}. {room['room_name']} - {room['streak']}연속")
            else:
                print("\n🔴 뱅커 연패 방: 없음")
    
    except Exception as e:
        print(f"응답 파싱 오류: {e}")
        print(f"원본 응답: {response.text}")

async def auto_setup(ws_url, user_id, monitoring_time=60):
    """WebSocket URL로부터 자동 설정 및 실행"""
    print("=== 바카라 모니터링 시작 ===")
    print("WebSocket URL에서 설정을 추출하여 모니터링을 시작합니다.")
    
    # URL에서 설정 추출
    config = extract_baccarat_config(ws_url)
    if not config:
        print("유효하지 않은 URL입니다. 종료합니다.")
        return
    
    # 사용자 ID 설정
    config["user_id"] = user_id
    
    print("\n추출된 설정 정보:")
    for key, value in config.items():
        print(f"  {key}: {value}")
    
    # 세션 설정 전송
    print("\n세션 설정 전송 중...")
    response = requests.post(f"{BASE_URL}/api/baccarat/config", json=config)
    if response.status_code != 200:
        print(f"세션 설정 전송 실패: {response.text}")
        return
    
    # 기본 연패 설정
    streak_settings = {
        "player_streak": 3,
        "banker_streak": 3,
        "min_results": 10,
        "user_id": user_id
    }
    
    print("\n연패 설정 전송 중...")
    response = requests.post(f"{BASE_URL}/api/baccarat/streak-settings", json=streak_settings)
    if response.status_code != 200:
        print(f"연패 설정 전송 실패: {response.text}")
        return
    
    # WebSocket 연결
    print("\nWebSocket 연결 시작...")
    websocket_task = asyncio.create_task(websocket_client(user_id))
    
    # 클라이언트 시작
    print("\n바카라 클라이언트 시작...")
    response = requests.post(f"{BASE_URL}/api/baccarat/start/{user_id}")
    if response.status_code != 200:
        print(f"클라이언트 시작 실패: {response.text}")
        websocket_task.cancel()
        try:
            await websocket_task
        except asyncio.CancelledError:
            pass
        return
    
    # 모니터링
    print(f"\n{monitoring_time}초간 모니터링 중...")
    print("(Ctrl+C를 누르면 즉시 종료)")
    try:
        for i in range(monitoring_time):
            if i % 10 == 0 and i > 0:
                # 10초마다 데이터 조회
                response = requests.get(f"{BASE_URL}/api/baccarat/data/{user_id}")
                data = response.json()
                if "monitor_data" in data and "streak_data" in data["monitor_data"]:
                    streak_data = data["monitor_data"]["streak_data"]
                    player_count = len(streak_data.get("player_streak_rooms", []))
                    banker_count = len(streak_data.get("banker_streak_rooms", []))
                    print(f"\n현재 감지된 연패 방 수: P:{player_count}, B:{banker_count}")
                    
                    # 연패 방이 있으면 상세 정보 출력
                    player_rooms = streak_data.get('player_streak_rooms', [])
                    if player_rooms:
                        print(f"  [플레이어 연패 방]")
                        for idx, room in enumerate(player_rooms[:3], 1):  # 최대 3개만 표시
                            print(f"    {idx}. {room['room_name']} - {room['streak']}연속")
                        if len(player_rooms) > 3:
                            print(f"    ... 외 {len(player_rooms) - 3}개")
                    
                    banker_rooms = streak_data.get('banker_streak_rooms', [])
                    if banker_rooms:
                        print(f"  [뱅커 연패 방]")
                        for idx, room in enumerate(banker_rooms[:3], 1):  # 최대 3개만 표시
                            print(f"    {idx}. {room['room_name']} - {room['streak']}연속")
                        if len(banker_rooms) > 3:
                            print(f"    ... 외 {len(banker_rooms) - 3}개")
            
            print(".", end="", flush=True)
            await asyncio.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단되었습니다.")
    finally:
        # 클라이언트 중지
        print("\n\n바카라 클라이언트 중지 중...")
        requests.post(f"{BASE_URL}/api/baccarat/stop/{user_id}")
        
        # WebSocket 연결 종료
        websocket_task.cancel()
        try:
            await websocket_task
        except asyncio.CancelledError:
            pass
        
        print("\n=== 바카라 모니터링 종료 ===")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='바카라 API 테스트 클라이언트')
    parser.add_argument('url', help='바카라 WebSocket URL (필수)')
    parser.add_argument('--user', '-i', default='test_user_1', help='사용자 ID')
    parser.add_argument('--time', '-t', type=int, default=60, help='모니터링 시간(초)')
    parser.add_argument('--server', '-s', default='http://localhost:8080', help='서버 URL')
    
    args = parser.parse_args()
    
    # 서버 URL 설정
    BASE_URL = args.server
    WS_URL = f"ws://{BASE_URL.replace('http://', '').replace('https://', '')}/ws/baccarat"
    
    # WebSocket URL이 제공되었는지 확인
    if not args.url:
        print("오류: 바카라 WebSocket URL이 필요합니다.")
        print("예시: python test_client.py \"wss://skylinestart.evo-games.com/public/lobby/socket/v2/...\"")
        sys.exit(1)
    
    # 자동 설정 모드로 실행
    asyncio.run(auto_setup(args.url, args.user, args.time))