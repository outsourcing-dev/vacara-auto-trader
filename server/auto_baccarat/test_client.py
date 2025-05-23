import asyncio
import websockets
import json
import requests
import time
import sys
from datetime import datetime
import argparse
from urllib.parse import urlparse, parse_qs, urlunparse

# 서버 URL 설정 (기본값)
BASE_URL = "http://localhost:8080"
WS_URL = "ws://localhost:8080/ws/baccarat"

def is_valid_url(url):
    """URL 유효성 검사"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def normalize_url(url):
    """URL 정규화"""
    if not url:
        return None
    
    # http:// 접두사 확인 및 추가
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url
    
    try:
        # URL 파싱 및 재구성
        parsed = urlparse(url)
        # 경로가 없으면 / 추가
        if not parsed.path:
            parts = list(parsed)
            parts[2] = "/"
            url = urlunparse(parts)
        return url
    except Exception as e:
        print(f"URL 정규화 오류: {e}")
        return None

def extract_baccarat_config(ws_url):
    """WebSocket URL에서 바카라 설정 정보 추출"""
    if not ws_url:
        print("WebSocket URL이 제공되지 않았습니다.")
        return None
    
    if not ws_url.startswith("ws://") and not ws_url.startswith("wss://"):
        print("유효하지 않은 WebSocket URL입니다. ws:// 또는 wss://로 시작해야 합니다.")
        return None
    
    try:
        # URL 파싱
        parsed_url = urlparse(ws_url)
        query_params = parse_qs(parsed_url.query)
        
        # 도메인 및 프로토콜 추출
        domain = parsed_url.netloc
        protocol = parsed_url.scheme
        
        # 경로에서 bare_session_id 추출
        path_parts = parsed_url.path.split('/')
        bare_session_id = path_parts[-1] if path_parts else ""
        
        # 쿼리 파라미터에서 값 추출
        session_id = query_params.get('EVOSESSIONID', [''])[0]
        
        # instance 파라미터 처리 (하이픈으로 분리된 첫 부분만 사용)
        instance_param = query_params.get('instance', [''])[0]
        instance = instance_param.split('-')[0] if instance_param else ''
        
        client_version = query_params.get('client_version', [''])[0]
        
        # 필수 값 확인
        missing_fields = []
        if not bare_session_id:
            missing_fields.append("bare_session_id")
        if not session_id:
            missing_fields.append("session_id")
        if not instance:
            missing_fields.append("instance")
        if not client_version:
            missing_fields.append("client_version")
        if not domain:
            missing_fields.append("domain")
        if not protocol:
            missing_fields.append("protocol")
            
        if missing_fields:
            error_msg = f"다음 필수 설정값이 URL에서 추출되지 않았습니다: {', '.join(missing_fields)}"
            print(error_msg)
            return None
        
        # 모든 필드가 있는 경우 설정 반환
        return {
            "session_id": session_id,
            "bare_session_id": bare_session_id,
            "instance": instance,
            "client_version": client_version,
            "domain": domain,
            "protocol": protocol
        }
    except Exception as e:
        print(f"URL 파싱 오류: {e}")
        return None


async def test_baccarat_api(user_id, ws_url=None, monitoring_time=None):
    print("=== 바카라 API 테스트 시작 ===")
    
    # 1. 세션 설정
    print("\n1. 세션 설정")
    
    if not ws_url:
        print("웹소켓 URL이 필요합니다.")
        return
    
    # URL에서 설정 추출
    config = extract_baccarat_config(ws_url)
    if not config:
        print("유효하지 않은 URL입니다. 필요한 모든 설정 정보가 포함된 URL을 제공해주세요.")
        return
    
    # 사용자 ID 추가
    config["user_id"] = user_id
    
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
    print("\n서버로 설정 전송 중...")
    try:
        response = requests.post(f"{BASE_URL}/api/baccarat/config", json=config)
        print_response(response)
        
        if response.status_code != 200:
            print("세션 설정 전송 실패. 프로그램을 종료합니다.")
            return
    except requests.exceptions.InvalidURL:
        print(f"유효하지 않은 서버 URL: {BASE_URL}")
        print("서버 URL 형식을 확인하세요. (예: http://localhost:8080)")
        return
    except requests.exceptions.ConnectionError:
        print(f"서버 연결 실패: {BASE_URL}")
        print("서버가 실행 중인지 확인하세요.")
        return
    except Exception as e:
        print(f"설정 전송 중 오류 발생: {e}")
        return
    
    # 연패 설정 전송
    streak_settings = {
        "player_streak": player_streak,
        "banker_streak": banker_streak,
        "min_results": min_results,
        "user_id": user_id
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/baccarat/streak-settings", json=streak_settings)
        print_response(response)
        
        if response.status_code != 200:
            print("연패 설정 전송 실패. 프로그램을 종료합니다.")
            return
    except Exception as e:
        print(f"연패 설정 전송 중 오류 발생: {e}")
        return
    
    # 3. WebSocket 연결 준비
    print("\n3. WebSocket 연결 시작")
    websocket_task = asyncio.create_task(websocket_client(user_id))
    
    # 4. 바카라 클라이언트 시작
    print("\n4. 바카라 클라이언트 시작")
    try:
        response = requests.post(f"{BASE_URL}/api/baccarat/start/{user_id}")
        print_response(response)
        
        if response.status_code != 200 or (hasattr(response, 'json') and response.json().get('status') == 'error'):
            print("바카라 클라이언트 시작 실패. 프로그램을 종료합니다.")
            websocket_task.cancel()
            try:
                await websocket_task
            except asyncio.CancelledError:
                pass
            return
    except Exception as e:
        print(f"클라이언트 시작 중 오류 발생: {e}")
        websocket_task.cancel()
        try:
            await websocket_task
        except asyncio.CancelledError:
            pass
        return
    
    # 5. 모니터링 (데이터 수집) - 무한 루프로 변경
    print("\n5. 무제한 모니터링 시작...")
    print("(Ctrl+C를 누르면 즉시 종료)")
    
    try:
        # 진행 표시 - 무한 루프로 변경
        i = 0
        while True:
            if i % 10 == 0 and i > 0:
                # 10초마다 현재 데이터 조회
                try:
                    response = requests.get(f"{BASE_URL}/api/baccarat/data/{user_id}")
                    print(f"\n현재 데이터 ({datetime.now().strftime('%H:%M:%S')}):")
                    
                    data = response.json()
                    if "monitor_data" in data and "streak_data" in data["monitor_data"]:
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
                    else:
                        print("  모니터링 데이터가 없습니다.")
                except Exception as e:
                    print(f"  데이터 조회 오류: {e}")
            
            print(".", end="", flush=True)
            await asyncio.sleep(1)
            i += 1  # 카운터 증가
    
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단되었습니다.")
        
    finally:
        # 6. 바카라 클라이언트 중지
        print("\n\n6. 바카라 클라이언트 중지")
        try:
            response = requests.post(f"{BASE_URL}/api/baccarat/stop/{user_id}")
            print_response(response)
        except Exception as e:
            print(f"클라이언트 중지 중 오류 발생: {e}")
        
        # 7. 최종 데이터 조회
        print("\n7. 최종 데이터 조회")
        try:
            response = requests.get(f"{BASE_URL}/api/baccarat/data/{user_id}")
            print_response(response, show_data=True)
        except Exception as e:
            print(f"데이터 조회 중 오류 발생: {e}")
        
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
        ws_url = f"{WS_URL}/{user_id}"
        print(f"WebSocket 연결 시도: {ws_url}")
        
        async with websockets.connect(ws_url) as websocket:
            print(f"WebSocket 연결 성공: {ws_url}")
            
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

def get_server_url():
    """서버 URL 설정"""
    default_url = "http://localhost:8080"
    server_url = input(f"서버 URL을 입력하세요 (기본값: {default_url}): ") or default_url
    
    # URL 정규화
    normalized_url = normalize_url(server_url)
    if not normalized_url:
        print(f"유효하지 않은 URL 형식: {server_url}")
        print(f"기본값 {default_url}을 사용합니다.")
        return default_url
    
    # URL 유효성 검사
    if not is_valid_url(normalized_url):
        print(f"유효하지 않은 URL: {normalized_url}")
        print(f"기본값 {default_url}을 사용합니다.")
        return default_url
    
    return normalized_url

async def test_baccarat_predictions(user_id, ws_url=None):
    print("=== 바카라 예측 테스트 시작 ===")

    # 1. 세션 설정
    print("\n1. 세션 설정")
    if not ws_url:
        print("웹소켓 URL이 필요합니다.")
        return

    # URL에서 설정 추출
    config = extract_baccarat_config(ws_url)
    if not config:
        print("유효하지 않은 URL입니다. 필요한 모든 설정 정보가 포함된 URL을 제공해주세요.")
        return

    # 사용자 ID 추가
    config["user_id"] = user_id

    print("\n추출된 설정 정보:")
    for key, value in config.items():
        print(f"  {key}: {value}")

    # 2. 테스트 데이터 준비
    print("\n2. 테스트 데이터 준비")
    test_results = [
        "P", "B", "P", "P", "B", "B", "P", "B", "P", "P",
        "B", "B", "P", "P", "B", "P", "B"  # 총 17개 데이터
    ]
    print(f"테스트 데이터 (총 {len(test_results)}개): {test_results}")

    # 3. ChoicePickEngine 초기화
    print("\n3. ChoicePickEngine 초기화")
    from prediction.choice_pick_engine import ChoicePickEngine
    engine = ChoicePickEngine()

    # 4. 데이터 추가 및 예측
    print("\n4. 데이터 추가 및 예측")
    predictions = []
    win_loss_results = []

    for i in range(len(test_results) - 15):
        # 최신 15개 데이터 추가
        recent_results = test_results[i:i + 15]
        engine.add_results(recent_results)

        # 예측 수행
        predicted_pick = engine.predict()
        actual_result = test_results[i + 15]

        # 예측 결과와 실제 결과 비교
        is_win = predicted_pick == actual_result
        win_loss_results.append("승" if is_win else "패")

        # 예측 픽 저장
        predictions.append(predicted_pick)

        # 로그 출력
        print(f"\n[예측 {i + 1}]")
        print(f"  최근 15개 데이터: {recent_results}")
        print(f"  예측 픽: {predicted_pick}")
        print(f"  실제 결과: {actual_result}")
        print(f"  결과: {'승' if is_win else '패'}")

    # 5. 결과 출력
    print("\n5. 최종 결과 출력")
    print("\n[15개 픽 - 예측 픽]")
    for i, (recent, pred) in enumerate(zip(test_results[:len(predictions)], predictions), 1):
        print(f"  {i}. {recent} → {pred}")

    print("\n[승/패 결과]")
    print("  " + " | ".join(win_loss_results))

    print("\n=== 바카라 예측 테스트 완료 ===")

if __name__ == "__main__":
    print("=== 바카라 자동 모니터링 클라이언트 ===")

    # 서버 URL 설정
    BASE_URL = get_server_url()
    WS_URL = f"ws://{BASE_URL.replace('http://', '').replace('https://', '')}/ws/baccarat"

    print(f"서버 URL: {BASE_URL}")
    print(f"WebSocket URL: {WS_URL}")

    # WebSocket URL 입력 받기
    print("\n바카라 WebSocket URL 입력")
    print("예시: wss://skylinestart.evo-games.com/public/lobby/socket/v2/...")
    ws_url = input("WebSocket URL: ")

    if not ws_url:
        print("\n오류: WebSocket URL이 필요합니다. 프로그램을 종료합니다.")
        sys.exit(1)

    # 사용자 ID 입력 받기
    user_id = input("\n사용자 ID를 입력하세요 (기본값: test_user_1): ") or "test_user_1"

    # 테스트 실행
    try:
        asyncio.run(test_baccarat_predictions(user_id, ws_url))
    except Exception as e:
        print(f"\n예상치 못한 오류 발생: {e}")
        sys.exit(1)