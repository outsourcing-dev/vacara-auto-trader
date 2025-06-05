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

async def continuous_streak_monitor(user_id, streak_count=3, check_interval=30):
    """
    연패 조건에 맞는 방이 나올 때까지 무한 루프로 모니터링
    
    Args:
        user_id: 사용자 ID
        streak_count: 연패 기준
        check_interval: 체크 간격 (초)
    """
    print(f"\n=== {streak_count}연패 방 무한 모니터링 시작 ===")
    print(f"체크 간격: {check_interval}초")
    print("조건에 맞는 방이 나올 때까지 계속 모니터링합니다...")
    print("중단하려면 Ctrl+C를 누르세요.\n")
    
    loop_count = 0
    start_time = datetime.now()
    
    try:
        while True:
            loop_count += 1
            current_time = datetime.now()
            elapsed = current_time - start_time
            
            print(f"[{current_time.strftime('%H:%M:%S')}] 🔍 {loop_count}번째 체크 (경과시간: {elapsed})")
            
            try:
                # 연패 방 분석 실행
                response = requests.post(
                    f"{BASE_URL}/api/baccarat/find-streak-rooms",
                    json={
                        "streak_count": streak_count,
                        "user_id": user_id
                    },
                    timeout=30  # 30초 타임아웃
                )
                
                if response.status_code == 200:
                    result = response.json()
                    total_found = result.get("total_found", 0)
                    streak_rooms = result.get("streak_rooms", [])
                    statistics = result.get("analysis_statistics", {})
                    
                    # 통계 정보 출력
                    total_rooms = statistics.get("total_rooms", 0)
                    sufficient_rooms = statistics.get("sufficient_data_rooms", 0)
                    
                    print(f"   📊 분석 완료: 총 {total_rooms}개 방 중 {sufficient_rooms}개 방 분석")
                    
                    if total_found > 0:
                        print(f"\n🎯 {streak_count}연패 조건 만족하는 방 발견! ({total_found}개)")
                        print("=" * 50)
                        
                        for i, room in enumerate(streak_rooms, 1):
                            print(f"{i}. 🏠 {room['room_name']}")
                            print(f"   📈 총 게임: {room['total_games']}게임")
                            print(f"   🔥 연패: {room['streak_failures']}회")
                            print(f"   🎲 예측: {room['predictions']}")
                            print(f"   ✅ 실제: {room['actual_results']}")
                            print(f"   📝 요약: {room['analysis_summary']}")
                            print()
                        
                        print("=" * 50)
                        print(f"✅ 모니터링 완료! {total_found}개 방에서 {streak_count}연패 조건 만족")
                        
                        # 첫 번째 방에 대한 추가 상세 정보
                        if len(streak_rooms) > 0:
                            first_room = streak_rooms[0]
                            print(f"\n🔍 첫 번째 방 상세 분석: {first_room['room_name']}")
                            await test_single_room_prediction(user_id, first_room['room_id'], streak_count)
                        
                        break  # 조건에 맞는 방을 찾았으므로 루프 종료
                    else:
                        print(f"   ❌ {streak_count}연패 조건에 맞는 방 없음")
                        
                        # 상위 연패 방이 있다면 표시
                        if statistics.get("sufficient_data_rooms", 0) > 0:
                            # 기존 연패 데이터 확인 (3연패 기준)
                            default_response = requests.post(
                                f"{BASE_URL}/api/baccarat/find-streak-rooms",
                                json={
                                    "streak_count": 3,
                                    "user_id": user_id
                                },
                                timeout=15
                            )
                            
                            if default_response.status_code == 200:
                                default_result = default_response.json()
                                default_rooms = default_result.get("streak_rooms", [])
                                if default_rooms:
                                    print(f"   💡 참고: 3연패 조건 만족 방은 {len(default_rooms)}개 있음")
                
                else:
                    print(f"   ⚠️ API 오류: {response.status_code}")
                    if response.status_code == 400:
                        error_data = response.json()
                        print(f"   오류 메시지: {error_data.get('detail', 'Unknown error')}")
                    
            except requests.exceptions.Timeout:
                print("   ⏰ 요청 타임아웃 (30초 초과)")
            except requests.exceptions.RequestException as e:
                print(f"   🔌 네트워크 오류: {e}")
            except Exception as e:
                print(f"   ❌ 예상치 못한 오류: {e}")
            
            # 다음 체크까지 대기
            print(f"   ⏳ {check_interval}초 후 다시 체크...")
            await asyncio.sleep(check_interval)
            
    except KeyboardInterrupt:
        print(f"\n\n⏹️  사용자에 의해 모니터링이 중단되었습니다.")
        print(f"📊 총 {loop_count}번 체크, 경과시간: {datetime.now() - start_time}")
    except Exception as e:
        print(f"\n❌ 모니터링 중 오류 발생: {e}")

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

async def test_baccarat_continuous_monitoring(user_id, ws_url=None):
    """바카라 무한 연패 모니터링 테스트"""
    
    print("=== 바카라 무한 연패 모니터링 시스템 ===")
    
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
    
    print("\n✅ 모니터링 시작됨. 초기 데이터 수집 중...")
    
    try:
        # 초기 데이터 수집을 위해 30초 대기
        await asyncio.sleep(30)
        
        # 연패 기준 설정
        try:
            streak_count = int(input("\n연패 기준을 입력하세요 (기본값: 3): ") or "3")
        except ValueError:
            streak_count = 3
        
        # 체크 간격 설정
        try:
            check_interval = int(input(f"체크 간격을 입력하세요 (초, 기본값: 30): ") or "30")
        except ValueError:
            check_interval = 30
        
        print(f"\n🎯 설정 완료:")
        print(f"   연패 기준: {streak_count}연패")
        print(f"   체크 간격: {check_interval}초")
        print(f"   필터링된 방: filtered_room_mappings.json 기준")
        
        # 무한 모니터링 시작
        await continuous_streak_monitor(user_id, streak_count, check_interval)
                
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단되었습니다.")
        
    finally:
        # 정리
        try:
            requests.post(f"{BASE_URL}/api/baccarat/stop/{user_id}")
            print("🛑 바카라 모니터링 중지됨")
        except:
            pass
        
        websocket_task.cancel()
        try:
            await websocket_task
        except asyncio.CancelledError:
            pass
        
        print("\n=== 시스템 종료 완료 ===")

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
                        
                        # WebSocket 업데이트는 조용히 처리 (필요시에만 출력)
                        # print(f"📡 실시간 업데이트: P:{player_count}, B:{banker_count}")
                    
                except Exception as e:
                    break
    
    except asyncio.CancelledError:
        raise
    except Exception as e:
        # WebSocket 연결 오류는 조용히 처리
        pass

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
    print("=== 바카라 무한 연패 모니터링 시스템 ===")
    print("📊 filtered_room_mappings.json 파일의 방들을 모니터링합니다")
    print("🔄 조건에 맞는 방이 나올 때까지 무한 루프로 동작합니다")
    print("⏹️  중단하려면 언제든 Ctrl+C를 누르세요")
    
    # 서버 URL 설정
    BASE_URL = get_server_url()
    WS_URL = f"ws://{BASE_URL.replace('http://', '').replace('https://', '')}/ws/baccarat"
    
    print(f"🌐 서버 URL: {BASE_URL}")
    
    # WebSocket URL 입력
    print("\n🔗 바카라 WebSocket URL을 입력하세요:")
    print("예시: wss://skylinestart.evo-games.com/public/lobby/socket/v2/...")
    ws_url = input("WebSocket URL: ")
    
    if not ws_url:
        print("\n❌ 오류: WebSocket URL이 필요합니다.")
        sys.exit(1)
    
    # 사용자 ID 입력
    user_id = input("\n👤 사용자 ID를 입력하세요 (기본값: test_user_1): ") or "test_user_1"
    
    # 무한 모니터링 시작
    try:
        asyncio.run(test_baccarat_continuous_monitoring(user_id, ws_url))
    except Exception as e:
        print(f"\n💥 예상치 못한 오류 발생: {e}")
        sys.exit(1)