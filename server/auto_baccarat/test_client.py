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
    
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url
    
    try:
        parsed = urlparse(url)
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
        parsed_url = urlparse(ws_url)
        query_params = parse_qs(parsed_url.query)
        
        domain = parsed_url.netloc
        protocol = parsed_url.scheme
        
        path_parts = parsed_url.path.split('/')
        bare_session_id = path_parts[-1] if path_parts else ""
        
        session_id = query_params.get('EVOSESSIONID', [''])[0]
        instance_param = query_params.get('instance', [''])[0]
        instance = instance_param.split('-')[0] if instance_param else ''
        client_version = query_params.get('client_version', [''])[0]
        
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

async def test_streak_analysis(user_id, streak_count=3):
    """연패 분석 테스트"""
    print(f"\n=== {streak_count}연패 방 분석 테스트 ===")
    
    # 1. 분석 통계 먼저 확인
    print("\n1. 분석 통계 조회")
    try:
        response = requests.get(
            f"{BASE_URL}/api/baccarat/streak-analysis-stats/{user_id}",
            params={"streak_count": streak_count}
        )
        
        if response.status_code == 200:
            stats = response.json()
            print(f"✅ 통계 조회 성공:")
            statistics = stats.get("statistics", {})
            print(f"   총 방 수: {statistics.get('total_rooms', 0)}개")
            print(f"   분석 가능: {statistics.get('sufficient_data_rooms', 0)}개")
            print(f"   데이터 부족: {statistics.get('insufficient_data_rooms', 0)}개")
            print(f"   최소 필요 게임 수: {statistics.get('min_required_games', 0)}게임")
        else:
            print(f"❌ 통계 조회 실패: {response.status_code}")
            print_response(response)
            return
            
    except Exception as e:
        print(f"❌ 통계 조회 오류: {e}")
        return
    
    # 2. 실제 연패 방 분석 실행
    print(f"\n2. {streak_count}연패 방 분석 실행")
    try:
        response = requests.post(
            f"{BASE_URL}/api/baccarat/find-streak-rooms",
            json={
                "streak_count": streak_count,
                "user_id": user_id
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 분석 완료!")
            
            total_found = result.get("total_found", 0)
            streak_rooms = result.get("streak_rooms", [])
            
            print(f"\n🎯 {streak_count}연패 조건 만족: {total_found}개 방")
            
            if streak_rooms:
                print("\n📋 연패 방 목록:")
                for i, room in enumerate(streak_rooms, 1):
                    print(f"   {i}. {room['room_name']}")
                    print(f"      - 총 게임: {room['total_games']}게임")
                    print(f"      - 연패: {room['streak_failures']}회")
                    print(f"      - 예측: {room['predictions']}")
                    print(f"      - 실제: {room['actual_results']}")
                    
                # 첫 번째 방 상세 테스트
                if len(streak_rooms) > 0:
                    first_room = streak_rooms[0]
                    print(f"\n3. 첫 번째 방 상세 테스트: {first_room['room_name']}")
                    await test_single_room_prediction(user_id, first_room['room_id'], streak_count)
            else:
                print("   조건에 맞는 방이 없습니다.")
                
        else:
            print(f"❌ 분석 실패: {response.status_code}")
            print_response(response)
            
    except Exception as e:
        print(f"❌ 분석 오류: {e}")

async def test_single_room_prediction(user_id, room_id, streak_count=3):
    """단일 방 예측 테스트"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/baccarat/room-prediction-test/{user_id}/{room_id}",
            params={"streak_count": streak_count}
        )
        
        if response.status_code == 200:
            result = response.json()
            
            print(f"📊 방 상세 분석 결과:")
            print(f"   방 이름: {result.get('room_name', 'Unknown')}")
            print(f"   총 게임: {result.get('total_games', 0)}게임")
            print(f"   결과 패턴: {result.get('filtered_results', '')}")
            print(f"   연패 조건 만족: {'✅' if result.get('is_streak_room') else '❌'}")
            
            detailed_log = result.get('detailed_log', '')
            if detailed_log:
                print(f"\n📝 상세 분석 로그:")
                for line in detailed_log.split('\n'):
                    if line.strip():
                        print(f"   {line}")
        else:
            print(f"❌ 방 테스트 실패: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 방 테스트 오류: {e}")

async def test_baccarat_api_with_streak_analysis(user_id, ws_url=None):
    """바카라 API + 연패 분석 통합 테스트"""
    
    print("=== 바카라 모니터링 + 연패 분석 테스트 ===")
    
    # 1. 세션 설정
    if not ws_url:
        print("웹소켓 URL이 필요합니다.")
        return
    
    config = extract_baccarat_config(ws_url)
    if not config:
        print("유효하지 않은 URL입니다.")
        return
    
    config["user_id"] = user_id
    
    # 설정 전송
    try:
        response = requests.post(f"{BASE_URL}/api/baccarat/config", json=config)
        if response.status_code != 200:
            print("세션 설정 전송 실패.")
            return
            
    except Exception as e:
        print(f"설정 전송 오류: {e}")
        return
    
    # WebSocket 연결 및 클라이언트 시작
    websocket_task = asyncio.create_task(websocket_client(user_id))
    
    try:
        response = requests.post(f"{BASE_URL}/api/baccarat/start/{user_id}")
        if response.status_code != 200:
            print("바카라 클라이언트 시작 실패.")
            websocket_task.cancel()
            return
    except Exception as e:
        print(f"클라이언트 시작 오류: {e}")
        websocket_task.cancel()
        return
    
    print("\n✅ 모니터링 시작됨. 데이터 수집 중...")
    
    try:
        # 데이터 수집을 위해 30초 대기
        await asyncio.sleep(30)
        
        # 연패 분석 테스트
        try:
            streak_count = int(input("\n연패 기준을 입력하세요 (기본값: 3): ") or "3")
        except ValueError:
            streak_count = 3
        
        await test_streak_analysis(user_id, streak_count)
        
        # 추가 분석 옵션
        while True:
            continue_analysis = input(f"\n다른 연패 기준으로 분석하시겠습니까? (y/n): ").lower()
            if continue_analysis == 'y':
                try:
                    new_streak_count = int(input("새로운 연패 기준: "))
                    await test_streak_analysis(user_id, new_streak_count)
                except ValueError:
                    print("유효하지 않은 입력입니다.")
            else:
                break
                
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단되었습니다.")
        
    finally:
        # 정리
        try:
            requests.post(f"{BASE_URL}/api/baccarat/stop/{user_id}")
        except:
            pass
        
        websocket_task.cancel()
        try:
            await websocket_task
        except asyncio.CancelledError:
            pass
        
        print("\n=== 테스트 완료 ===")

async def websocket_client(user_id):
    """WebSocket 클라이언트"""
    try:
        ws_url = f"{WS_URL}/{user_id}"
        
        async with websockets.connect(ws_url) as websocket:
            while True:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    msg_type = data.get("type", "")
                    
                    if msg_type == "data_update" and "streak_data" in data:
                        streak_data = data["streak_data"]
                        player_count = len(streak_data.get("player_streak_rooms", []))
                        banker_count = len(streak_data.get("banker_streak_rooms", []))
                        
                        if player_count > 0 or banker_count > 0:
                            print(f"\n📊 WebSocket 업데이트: P:{player_count}, B:{banker_count} 방 감지")
                    
                except Exception as e:
                    break
    
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"WebSocket 연결 오류: {e}")

def print_response(response, show_data=False):
    """API 응답 출력"""
    try:
        data = response.json()
        if "status" in data:
            print(f"상태: {data['status']}")
        if "message" in data:
            print(f"메시지: {data['message']}")
        
        if show_data and "monitor_data" in data:
            monitor_data = data["monitor_data"]
            streak_data = monitor_data.get("streak_data", {})
            
            player_rooms = streak_data.get("player_streak_rooms", [])
            if player_rooms:
                print(f"\n🔵 플레이어 연패 방 ({len(player_rooms)}개):")
                for i, room in enumerate(player_rooms, 1):
                    print(f"  {i}. {room['room_name']} - {room['streak']}연속")
            
            banker_rooms = streak_data.get("banker_streak_rooms", [])
            if banker_rooms:
                print(f"\n🔴 뱅커 연패 방 ({len(banker_rooms)}개):")
                for i, room in enumerate(banker_rooms, 1):
                    print(f"  {i}. {room['room_name']} - {room['streak']}연속")
    
    except Exception as e:
        print(f"응답 파싱 오류: {e}")

def get_server_url():
    """서버 URL 설정"""
    default_url = "http://localhost:8080"
    server_url = input(f"서버 URL을 입력하세요 (기본값: {default_url}): ") or default_url
    
    normalized_url = normalize_url(server_url)
    if not normalized_url or not is_valid_url(normalized_url):
        print(f"기본값 {default_url}을 사용합니다.")
        return default_url
    
    return normalized_url

if __name__ == "__main__":
    print("=== 바카라 자동 모니터링 + 연패 분석 클라이언트 ===")
    
    # 서버 URL 설정
    BASE_URL = get_server_url()
    WS_URL = f"ws://{BASE_URL.replace('http://', '').replace('https://', '')}/ws/baccarat"
    
    print(f"서버 URL: {BASE_URL}")
    
    # WebSocket URL 입력
    print("\n바카라 WebSocket URL을 입력하세요:")
    print("예시: wss://skylinestart.evo-games.com/public/lobby/socket/v2/...")
    ws_url = input("WebSocket URL: ")
    
    if not ws_url:
        print("\n오류: WebSocket URL이 필요합니다.")
        sys.exit(1)
    
    # 사용자 ID 입력
    user_id = input("\n사용자 ID를 입력하세요 (기본값: test_user_1): ") or "test_user_1"
    
    # 테스트 실행
    try:
        asyncio.run(test_baccarat_api_with_streak_analysis(user_id, ws_url))
    except Exception as e:
        print(f"\n예상치 못한 오류 발생: {e}")
        sys.exit(1)