## 9. 주의사항

- 세션값은 주기적으로 만료될 수 있으므로, 연결이 끊어지면 새로운 세션값을 얻어 설정 파일을 업데이트해야 합니다.
- 실시간 데이터는 콘솔에만 출력되며, 별도의 저장/분석 기능은 아직 구현되지 않았습니다.
- 현재 버전은 데이터 수신만 가능하며 베팅 기능은 지원하지 않습니다.
- 방 ID와 이름 매핑은 지속적으로 업데이트해야 할 수 있습니다. 새로운 방이 추가되면 `room_mappings.json` 파일을 업데이트하세요.# 바카라 로비 데이터 수신기 사용 가이드

이 문서는 바카라 로비 데이터 수신기의 설정 및 사용 방법을 설명합니다.

## 1. 개요

바카라 로비 데이터 수신기는 EvoGames 바카라 로비의 실시간 데이터를 WebSocket을 통해 수신하고 콘솔에 출력하는 도구입니다. 각 방의 ID와 결과값을 실시간으로 받아볼 수 있습니다.

## 2. 설치 방법

프로그램 실행을 위해 필요한 라이브러리 설치:

```bash
pip install -r requirements.txt
```

이 명령은 다음 라이브러리를 설치합니다:
- websockets: WebSocket 클라이언트/서버 구현
- asyncio: 비동기 I/O 지원
- python-dotenv: 환경 변수 로드 (향후 확장성 고려)

## 3. 설정 파일

`config.json` 파일에 다음 정보를 입력해야 합니다:

```json
{
    "session_id": "your_session_id_here",
    "bare_session_id": "your_bare_session_id_here",
    "instance": "your_instance_here",
    "client_version": "your_client_version_here"
}
```

### 설정값 설명:

- `session_id`: EvoGames 세션 ID (EVOSESSIONID 쿠키값)
- `bare_session_id`: 순수 세션 ID
- `instance`: 인스턴스 정보
- `client_version`: 클라이언트 버전

## 4. 세션값 얻는 방법

필요한 세션값은 다음 단계를 통해 얻을 수 있습니다:

1. 웹 브라우저에서 바카라 로비 페이지 접속
2. 개발자 도구 열기 (F12 또는 Ctrl+Shift+I)
3. 네트워크 탭 선택
4. WebSocket 연결 찾기 (URL에 "socket" 포함)
5. 해당 연결의 URL에서 필요한 매개변수 추출:
   - `session_id`: 쿠키의 "EVOSESSIONID" 값 (요청 헤더의 Cookie 항목에서 확인)
   - `bare_session_id`: URL 경로에서 "/v2/" 다음 값
   - `instance`: URL의 "instance=" 다음 값
   - `client_version`: URL의 "client_version=" 다음 값

### 중요: 브라우저 헤더 정보

WebSocket 연결 시 서버는 다음 헤더 정보를 확인합니다:
- Origin: https://skylinestart.evo-games.com
- User-Agent: (브라우저 정보)
- Cookie: EVOSESSIONID=세션값

이 프로그램은 자동으로 이러한 헤더를 포함하여 연결합니다.

## 5. 실행 방법

기본 설정 파일(config.json)을 사용하여 실행:

```bash
python main.py
```

다른 설정 파일을 지정하여 실행:

```bash
python main.py --config custom_config.json
```

디버그 모드로 실행 (상세 로깅):
```bash
python main.py --debug
```

필터링 기능 비활성화:
```bash
python main.py --filter-off
```

명령줄에서 추가 필터 키워드 지정:
```bash
python main.py --keyword Speed --keyword 스피드
```

## 6. 출력 예시

정상 실행 시 다음과 같은 출력이 표시됩니다:

```
┌─────────────────────────────────────────────┐
│         바카라 로비 데이터 수신기          │
│       Baccarat Lobby Data Receiver         │
└─────────────────────────────────────────────┘

2025-05-14 10:30:00,123 - baccarat_client - INFO - Connecting to WebSocket server...
2025-05-14 10:30:01,456 - baccarat_client - INFO - ✅ WebSocket 연결 완료
2025-05-14 10:30:05,789 - baccarat_client - INFO - 📩 방 ID: peekbaccarat0001 결과 수신: [...]
2025-05-14 10:30:08,901 - baccarat_client - INFO - 📩 방 ID: peekbaccarat0002 결과 수신: [...]
...
```

## 7. 프로그램 종료 및 문제 해결

### 프로그램 종료
프로그램 실행 중 `Ctrl+C`를 누르면 안전하게 종료됩니다.

### 일반적인 문제 해결

#### 1. HTTP 403 Forbidden 에러
연결 시도 중 다음과 같은 오류가 표시되는 경우:
```
ERROR - Connection error: HTTP 403 Forbidden
ERROR - HTTP 403 Forbidden 에러 발생: 인증 헤더가 올바르지 않거나 세션이 만료되었을 수 있습니다.
```

**해결 방법:**
- 최신 세션 ID로 설정 업데이트: `python session_manager.py --update`
- 브라우저에서 로그인 후, 개발자 도구를 통해 새 세션 ID 확인 (네트워크 탭 → WebSocket 연결 → 요청 헤더)

#### 2. 연결은 성공하지만 데이터가 수신되지 않음
이 경우 다음을 확인하세요:
- 세션이 아직 유효한지 확인 (브라우저에서 바카라 로비 페이지 접속이 되는지)
- 모든 설정 값이 올바르게 입력되었는지 확인
- 프로그램을 재시작해보세요

## 8. 방 이름 매핑 및 필터링

### 방 이름 매핑
실제 방 ID를 사람이 읽기 쉬운 이름으로 매핑할 수 있습니다. `room_mappings.json` 파일을 수정하여 매핑을 추가하세요:

```json
{
    "room_mappings": {
        "qgqrrnuqvltnvejx": "Speed Baccarat A",
        "leqhceumaq6qfoug": "Lightning Baccarat",
        "LightningDT00001": "Lightning Dice"
    }
}
```

### 방 필터링
특정 키워드가 포함된 방만 표시하려면 `room_mappings.json` 파일의 `filter_keywords` 값을 설정하세요:

```json
{
    "filter_keywords": ["Speed", "스피드"]
}
```

이 설정은 "Speed" 또는 "스피드"가 포함된 방 이름만 표시합니다.

### 필터 설정 변경
명령줄에서 필터링을 임시로 비활성화하거나 키워드를 추가할 수 있습니다:

```bash
# 필터링 비활성화 (모든 방 표시)
python main.py --filter-off

# 키워드 추가
python main.py --keyword Speed --keyword 스피드
```

### 필터링 동작 방식
1. 방 ID가 매핑 목록에 있으면 해당 이름으로 변환됩니다.
2. 필터 키워드가 설정된 경우, 변환된 이름에 키워드가 포함된 방만 표시됩니다.
3. 필터 키워드가 없거나 `--filter-off` 옵션을 사용하면 모든 방이 표시됩니다.