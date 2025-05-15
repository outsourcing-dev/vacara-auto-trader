import asyncio
import websockets
import json
import requests
import time
import re
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# 서버 URL 설정
BASE_URL = "http://localhost:8080"
WS_URL = "ws://localhost:8080/ws/baccarat"

# 테스트 사용자 ID
USER_ID = "test_user_1"

def extract_baccarat_config(ws_url):
    """WebSocket URL에서 바카라 설정 정보를 추출합니다."""
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
            "client_version": client_version,
            "user_id": USER_ID
        }
    except Exception as e:
        print(f"URL 파싱 오류: {e}")
        return None

async def test_baccarat_api():
    print("=== 바카라 API 테스트 시작 ===")
    
    # WebSocket URL 입력 받기
    print("\n입력 안내:")
    print("바카라 WebSocket URL을 입력하세요. 예시 형식:")
    print("wss://skylinestart.evo-games.com/public/lobby/socket/v2/s2rqzokhx5pxl6z6?messageFormat=json&device=Desktop&features=opensAt%2CmultipleHero%2CshortThumbnails%2CskipInfosPublished%2Csmc%2CuniRouletteHistory%2CbacHistoryV2%2Cfilters%2CtableDecorations&instance=7lwa0y-s2rqzokhx5pxl6z6-&EVOSESSIONID=s2rqzokhx5pxl6z6s3gwwsr2ynjfu62m029164bfe2f358b6214e0765d7ab5fa955eaae2fea107d75&client_version=6.20250512.70248.51685-c40cdf22de")
    print("\n(빈 입력 시 기본값 사용)")
    
    ws_url = input("\nWebSocket URL: ").strip()
    
    # 기본값 사용
    if not ws_url:
        print("기본값 사용")
        config = {
            "session_id": "s2rqzokhx5pxl6z6s3gwwsr2ynjfu62m029164bfe2f358b6214e0765d7ab5fa955eaae2fea107d75",
            "bare_session_id": "s2rqzokhx5pxl6z6",
            "instance": "7lwa0y",
            "client_version": "6.20250512.70248.51685-c40cdf22de",
            "user_id": USER_ID
        }
    else:
        # URL에서 설정 추출
        config = extract_baccarat_config(ws_url)
        if not config:
            print("유효하지 않은 URL입니다. 기본값을 사용합니다.")
            config = {
                "session_id": "s2rqzokhx5pxl6z6s3gwwsr2ynjfu62m029164bfe2f358b6214e0765d7ab5fa955eaae2fea107d75",
                "bare_session_id": "s2rqzokhx5pxl6z6",
                "instance": "7lwa0y",
                "client_version": "6.20250512.70248.51685-c40cdf22de",
                "user_id": USER_ID
            }
    
    print("\n추출된 설정 정보:")
    for key, value in config.items():
        print(f"  {key}: {value}")
    
    # 연속 횟수 설정
    print("\n연패 감지 설정:")
    try:
        player_streak = int(input("플레이어 연패 감지 횟수 (기본값 3): ") or "3")
        banker_streak = int(input("뱅커 연패 감지 횟수 (기본값 3): ") or "3")
        min_results = int(input("최소 결과 수 (기본값 10): ") or "10")
    except ValueError:
        print("유효하지 않은 입력입니다. 기본값을 사용합니다.")
        player_streak = 3
        banker_streak = 3
        min_results = 10
    
    # 모니터링 시간 설정
    try:
        monitoring_time = int(input("모니터링 시간(초) (기본값 60): ") or "60")
    except ValueError:
        print("유효하지 않은 입력입니다. 기본값 60초를 사용합니다.")
        monitoring_time = 60
    
    # 1. 세션 설정
    print("\n1. 세션 설정 전송")
    response = requests.post(f"{BASE_URL}/api/baccarat/config", json=config)
    print_response(response)
    
    # 2. 연패 설정
    print("\n2. 연패 설정 전송")
    streak_settings = {
        "player_streak": player_streak,
        "banker_streak": banker_streak,
        "min_results": min_results,
        "user_id": USER_ID
    }
    
    response = requests.post(f"{BASE_URL}/api/baccarat/streak-settings", json=streak_settings)
    print_response(response)
    
    # 3. WebSocket 연결 준비
    print("\n3. WebSocket 연결 시작")
    websocket_task = asyncio.create_task(websocket_client())
    
    # 4. 바카라 클라이언트 시작
    print("\n4. 바카라 클라이언트 시작")
    response = requests.post(f"{BASE_URL}/api/baccarat/start/{USER_ID}")
    print_response(response)
    
    # 5. 모니터링 (데이터 수집)
    print(f"\n5. {monitoring_time}초간 데이터 수집 중...")
    
    # 진행 표시
    for i in range(monitoring_time):
        if i % 10 == 0:
            # 10초마다 현재 데이터 조회
            response = requests.get(f"{BASE_URL}/api/baccarat/data/{USER_ID}")
            print(f"\n현재 데이터 ({datetime.now().strftime('%H:%M:%S')}):")
            data = response.json()
            if "streak_data" in data:
                streak_data = data["streak_data"]
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
    response = requests.post(f"{BASE_URL}/api/baccarat/stop/{USER_ID}")
    print_response(response)
    
    # 7. 최종 데이터 조회
    print("\n7. 최종 데이터 조회")
    response = requests.get(f"{BASE_URL}/api/baccarat/data/{USER_ID}")
    print_response(response, show_data=True)
    
    # WebSocket 태스크 종료
    websocket_task.cancel()
    try:
        await websocket_task
    except asyncio.CancelledError:
        pass
    
    print("\n=== 바카라 API 테스트 완료 ===")

async def websocket_client():
    """WebSocket 클라이언트"""
    try:
        async with websockets.connect(f"{WS_URL}/{USER_ID}") as websocket:
            print(f"WebSocket 연결 성공: {WS_URL}/{USER_ID}")
            
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
                        streak_data = data.get("streak_data", {})
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
        
        if show_data and "streak_data" in data:
            streak_data = data["streak_data"]
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

if __name__ == "__main__":
    asyncio.run(test_baccarat_api())