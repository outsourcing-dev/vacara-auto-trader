# Vacara Auto Baccarat API 서버

바카라 로비에서 실시간으로 게임 결과를 모니터링하고, 연패 패턴을 감지하며, 조건에 맞는 방에서 자동 베팅을 실행하는 API 서버입니다.

## 주요 기능

1. **로비 모니터링**: 모든 바카라 방의 게임 결과를 실시간으로 수집
2. **연패 감지**: 사용자 설정 조건에 맞는 연패 중인 방 필터링
3. **베팅 자동화**: 특정 방에 입장하여 연패 전략에 따른 자동 베팅 실행
4. **예측 알고리즘**: 다양한 게임 패턴 분석 및 예측

## 디렉토리 구조

```
server/auto_baccarat/
├── common/                # 공통 모듈
│   ├── config.py          # 기본 설정
│   └── __init__.py
├── monitor/               # 로비 모니터링 모듈
│   ├── lobby_monitor.py   # 로비 모니터링 클래스
│   └── __init__.py
├── betting/               # 베팅 실행 모듈
│   ├── bet_executor.py    # 베팅 실행 클래스
│   └── __init__.py
├── prediction/            # 예측 알고리즘 모듈
│   ├── prediction_engine.py  # 예측 엔진 클래스
│   └── __init__.py
├── utils/                 # 유틸리티 모듈
│   ├── url_extractor.py   # URL 파싱 유틸리티
│   └── __init__.py
├── server.py              # 메인 서버 파일
├── test_client.py         # 테스트용 클라이언트
└── requirements.txt       # 패키지 의존성
```

## 사용 방법

### 1. 설치

```bash
pip install -r requirements.txt
```

### 2. 서버 실행

```bash
cd server/auto_baccarat
python server.py
```

### 3. API 사용

#### 3.1 세션 설정

```bash
curl -X POST http://localhost:8080/api/baccarat/config \
  -H "Content-Type: application/json" \
  -d '{"session_id": "your_session_id", "bare_session_id": "your_bare_session_id", "instance": "your_instance", "client_version": "your_client_version", "user_id": "user1"}'
```

#### 3.2 연패 설정

```bash
curl -X POST http://localhost:8080/api/baccarat/streak-settings \
  -H "Content-Type: application/json" \
  -d '{"player_streak": 3, "banker_streak": 3, "min_results": 10, "user_id": "user1"}'
```

#### 3.3 모니터링 시작

```bash
curl -X POST http://localhost:8080/api/baccarat/start/user1
```

#### 3.4 베팅 설정

```bash
curl -X POST http://localhost:8080/api/baccarat/betting-config \
  -H "Content-Type: application/json" \
  -d '{"room_id": "room123", "room_websocket_url": "wss://...", "user_id": "user1", "amount": 1000, "max_rounds": 10, "strategy": "follow_streak"}'
```

#### 3.5 베팅 시작

```bash
curl -X POST http://localhost:8080/api/baccarat/betting/start/user1/room123
```

## WebSocket 엔드포인트

- 모니터링 데이터: `ws://localhost:8080/ws/baccarat/{user_id}`
- 베팅 데이터: `ws://localhost:8080/ws/betting/{user_id}/{room_id}`

## 환경설정

실행 환경에 따라 다음 설정을 수정하세요:

- `common/config.py`: 기본 설정 값
- `filtered_room_mappings.json`: 필터링된 방 매핑 (ID와 이름)

## 라이센스

이 프로젝트는 비공개 소프트웨어입니다.