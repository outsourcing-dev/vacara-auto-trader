import asyncio
import websockets
import json
import requests
import threading
import queue
import sys
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# 서버 URL 설정 (기본값)
BASE_URL = "http://localhost:8080"
WS_URL = "ws://localhost:8080/ws/baccarat"

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
        
        # 도메인 및 프로토콜 추출
        domain = parsed_url.netloc
        protocol = parsed_url.scheme
        
        # 경로에서 bare_session_id 추출
        path_parts = parsed_url.path.split('/')
        bare_session_id = path_parts[-1] if path_parts else ""
        
        # 쿼리 파라미터에서 값 추출
        session_id = query_params.get('EVOSESSIONID', [''])[0]
        
        # instance 파라미터 처리
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

class InteractiveMonitor:
    def __init__(self, user_id):
        self.user_id = user_id
        self.running = False
        self.command_queue = queue.Queue()
        self.websocket_task = None
        
    def input_thread(self):
        """사용자 입력을 받는 별도 스레드"""
        while self.running:
            try:
                user_input = input().strip().lower()
                self.command_queue.put(user_input)
                if user_input in ['q', 'quit']:
                    break
            except EOFError:
                break
            except Exception as e:
                print(f"입력 오류: {e}")
    
    async def start_monitoring(self):
        """모니터링 시작"""
        self.running = True
        
        # 입력 스레드 시작
        input_thread = threading.Thread(target=self.input_thread, daemon=True)
        input_thread.start()
        
        # WebSocket 연결 시작
        self.websocket_task = asyncio.create_task(self.websocket_client())
        
        print("\n🚀 대화형 모니터링 시작!")
        print("명령어:")
        print("  's' 또는 'summary': 방 요약 정보 출력")
        print("  'r <room_id>': 특정 방 상세 정보 출력")
        print("  'status': 현재 상태 확인")
        print("  'q' 또는 'quit': 종료")
        print("=" * 50)
        
        i = 0
        try:
            while self.running:
                # 명령어 처리
                try:
                    while not self.command_queue.empty():
                        command = self.command_queue.get_nowait()
                        await self.handle_command(command)
                        if command in ['q', 'quit']:
                            self.running = False
                            break
                except queue.Empty:
                    pass
                
                # 30초마다 자동 요약
                if i % 30 == 0 and i > 0:
                    await self.show_summary()
                
                # 진행 상태 표시
                if i % 10 == 0:
                    print(f"\n⏰ 모니터링 중... ({i}초 경과) [명령어 입력 후 Enter]")
                
                await asyncio.sleep(1)
                i += 1
                
        except KeyboardInterrupt:
            print("\n\n🛑 사용자에 의해 중단되었습니다.")
        finally:
            self.running = False
            
            # WebSocket 태스크 종료
            if self.websocket_task:
                self.websocket_task.cancel()
                try:
                    await self.websocket_task
                except asyncio.CancelledError:
                    pass
    
    async def handle_command(self, command):
        """명령어 처리"""
        if command in ['s', 'summary']:
            await self.show_summary()
        elif command.startswith('r '):
            # 방 상세 정보
            try:
                room_id = command.split(' ', 1)[1]
                await self.show_room_detail(room_id)
            except IndexError:
                print("❌ 사용법: r <room_id>")
        elif command == 'status':
            await self.show_status()
        elif command in ['q', 'quit']:
            print("👋 종료 명령을 받았습니다.")
        elif command.strip():  # 빈 명령어가 아닌 경우
            print(f"❓ 알 수 없는 명령어: '{command}'")
            print("💡 도움말: 's' (요약), 'r <room_id>' (상세), 'status' (상태), 'q' (종료)")
    
    async def show_summary(self):
        """방 요약 정보 출력"""
        try:
            response = requests.get(f"{BASE_URL}/api/baccarat/summary/{self.user_id}")
            data = response.json()
            
            if data.get('status') == 'success':
                rooms = data.get('rooms', [])
                total_rooms = data.get('total_rooms', 0)
                
                print(f"\n📊 현재 모니터링 중인 방 ({total_rooms}개):")
                print("=" * 80)
                
                if rooms:
                    for idx, room in enumerate(rooms, 1):
                        recent_pattern = room.get('recent_15', room.get('result_pattern', ''))[-15:]
                        print(f"{idx:2d}. {room['room_name']}")
                        print(f"    게임 수: {room['total_games']}개 | 최근 15게임: {recent_pattern}")
                        print("-" * 60)
                    
                    print(f"\n📈 패턴 범례: P=Player 승, B=Banker 승, T=Tie")
                    print(f"🕐 업데이트: {datetime.now().strftime('%H:%M:%S')}")
                else:
                    print("📝 필터링된 방이 없습니다.")
            else:
                print(f"❌ 요약 정보 조회 실패: {data.get('message', '알 수 없는 오류')}")
                
        except Exception as e:
            print(f"❌ 요약 정보 조회 중 오류: {e}")
    
    async def show_room_detail(self, room_id):
        """특정 방 상세 정보 출력"""
        try:
            response = requests.get(f"{BASE_URL}/api/baccarat/room-data/{self.user_id}/{room_id}")
            data = response.json()
            
            if data.get('status') == 'success':
                print(f"\n🎰 방 상세 정보")
                print("=" * 60)
                print(f"방 이름: {data.get('room_name', 'N/A')}")
                print(f"방 ID: {data.get('room_id', 'N/A')}")
                print(f"총 게임 수: {data.get('total_games', 0)}개")
                print(f"전체 패턴: {data.get('result_pattern', 'N/A')}")
                print(f"최근 20게임: {data.get('recent_20', 'N/A')}")
                
                stats = data.get('stats', {})
                if stats:
                    print(f"\n📊 통계:")
                    print(f"  Player 승: {stats.get('player_wins', 0)}회 ({stats.get('player_rate', 0):.1f}%)")
                    print(f"  Banker 승: {stats.get('banker_wins', 0)}회 ({stats.get('banker_rate', 0):.1f}%)")
                    print(f"  Tie: {stats.get('ties', 0)}회 ({stats.get('tie_rate', 0):.1f}%)")
                
                print("-" * 60)
            else:
                print(f"❌ 방 정보 조회 실패: {data.get('message', '알 수 없는 오류')}")
                
        except Exception as e:
            print(f"❌ 방 정보 조회 중 오류: {e}")
    
    async def show_status(self):
        """현재 상태 확인"""
        try:
            response = requests.get(f"{BASE_URL}/api/baccarat/data/{self.user_id}")
            data = response.json()
            
            if data.get('status') == 'success':
                is_running = data.get('is_running', False)
                monitor_data = data.get('monitor_data', {})
                total_rooms = monitor_data.get('total_rooms', 0)
                
                print(f"\n📈 시스템 상태:")
                print(f"  모니터링 상태: {'🟢 실행 중' if is_running else '🔴 중지됨'}")
                print(f"  감지된 방 수: {total_rooms}개")
                print(f"  마지막 업데이트: {monitor_data.get('updated_at', 'N/A')}")
            else:
                print(f"❌ 상태 조회 실패: {data.get('message', '알 수 없는 오류')}")
                
        except Exception as e:
            print(f"❌ 상태 조회 중 오류: {e}")
    
    async def websocket_client(self):
        """WebSocket 클라이언트"""
        try:
            ws_url = f"{WS_URL}/{self.user_id}"
            
            async with websockets.connect(ws_url) as websocket:
                print(f"🔗 WebSocket 연결 성공")
                
                # 메시지 수신 루프
                while self.running:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(message)
                        
                        msg_type = data.get("type", "")
                        
                        # 데이터 업데이트 메시지 처리
                        if msg_type == "data_update":
                            filtered_rooms = data.get("filtered_rooms", [])
                            total_rooms = data.get("total_rooms", 0)
                            
                            if total_rooms > 0:
                                print(f"\n🔄 실시간 업데이트: {total_rooms}개 방 데이터 갱신됨")
                                
                                # 간단한 요약만 출력
                                for room in filtered_rooms[:3]:  # 상위 3개만
                                    recent = room.get('recent_15', '')[-15:]  # 최근 5게임만
                                    print(f"  📍 {room['room_name']}: {room['total_games']}게임, 최근15: {recent}")
                                
                                if total_rooms > 3:
                                    print(f"  ... 외 {total_rooms - 3}개 방")
                        
                        # 상태 업데이트 메시지 처리
                        elif msg_type == "status_update":
                            is_running = data.get("is_running", False)
                            status_text = "🟢 실행 중" if is_running else "🔴 중지됨"
                            print(f"\n📡 상태 변경: {status_text}")
                        
                        # 초기 데이터 처리
                        elif msg_type == "init_data":
                            monitor_data = data.get("monitor_data", {})
                            total_rooms = monitor_data.get("total_rooms", 0)
                            print(f"\n📋 초기 데이터 수신: {total_rooms}개 방 감지됨")
                        
                    except asyncio.TimeoutError:
                        # 타임아웃은 정상 (1초마다 체크)
                        continue
                    except Exception as e:
                        print(f"WebSocket 메시지 처리 오류: {e}")
                        break
        
        except asyncio.CancelledError:
            print("🔌 WebSocket 연결 종료")
            raise
        except Exception as e:
            print(f"❌ WebSocket 연결 오류: {e}")

async def main():
    print("=== 대화형 바카라 모니터링 클라이언트 (Windows 호환) ===")
    print("기능: 실시간 명령어 입력 및 필터링된 방 모니터링")
    print("=" * 60)

    # 서버 URL 설정
    global BASE_URL, WS_URL
    default_url = "http://localhost:8080"
    print(f"서버 URL (기본값: {default_url}): ", end="")
    
    try:
        server_url = input() or default_url
        if not server_url.startswith("http"):
            server_url = "http://" + server_url
        
        BASE_URL = server_url
        WS_URL = f"ws://{server_url.replace('http://', '').replace('https://', '')}/ws/baccarat"
    except KeyboardInterrupt:
        BASE_URL = default_url
        WS_URL = f"ws://{default_url.replace('http://', '')}/ws/baccarat"

    print(f"서버 URL: {BASE_URL}")

    # WebSocket URL 입력 받기
    print("\n바카라 WebSocket URL 입력")
    print("예시: wss://skylinestart.evo-games.com/public/lobby/socket/v2/...")
    ws_url = input("WebSocket URL: ")

    if not ws_url:
        print("\n❌ WebSocket URL이 필요합니다. 프로그램을 종료합니다.")
        return

    # 사용자 ID 입력 받기
    user_id = input("\n사용자 ID를 입력하세요 (기본값: test_user_1): ") or "test_user_1"

    # 1. 세션 설정
    print("\n1. 세션 설정")
    config = extract_baccarat_config(ws_url)
    if not config:
        print("❌ 유효하지 않은 URL입니다.")
        return

    config["user_id"] = user_id
    
    print("\n추출된 설정 정보:")
    for key, value in config.items():
        print(f"  {key}: {value}")

    # 설정 전송
    try:
        response = requests.post(f"{BASE_URL}/api/baccarat/config", json=config)
        if response.status_code != 200:
            print("❌ 세션 설정 실패")
            return
        print("✅ 세션 설정 완료")
    except Exception as e:
        print(f"❌ 서버 연결 실패: {e}")
        return

    # 2. 클라이언트 시작
    print("\n2. 바카라 클라이언트 시작")
    try:
        response = requests.post(f"{BASE_URL}/api/baccarat/start/{user_id}")
        if response.status_code != 200:
            print("❌ 클라이언트 시작 실패")
            return
        print("✅ 클라이언트 시작 완료")
    except Exception as e:
        print(f"❌ 클라이언트 시작 오류: {e}")
        return

    # 3. 대화형 모니터링 시작
    monitor = InteractiveMonitor(user_id)
    
    try:
        await monitor.start_monitoring()
    except Exception as e:
        print(f"\n❌ 모니터링 중 오류: {e}")
    finally:
        # 4. 정리 작업
        print("\n🔄 정리 작업 중...")
        try:
            response = requests.post(f"{BASE_URL}/api/baccarat/stop/{user_id}")
            print("✅ 클라이언트 중지 완료")
        except Exception as e:
            print(f"❌ 클라이언트 중지 오류: {e}")
        
        print("\n=== 대화형 바카라 모니터링 완료 ===")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 프로그램이 종료되었습니다.")
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {e}")
        sys.exit(1)