import asyncio
import sys
import os
import logging
import argparse
from client_ws import load_config, run_client

# 상위 디렉토리 모듈 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("baccarat_main")

async def main():
    """메인 실행 함수"""
    # 명령줄 인자 파싱
    parser = argparse.ArgumentParser(description='Baccarat Lobby Data Receiver')
    parser.add_argument('--config', '-c', default='config.json', help='Configuration file path')
    parser.add_argument('--debug', '-d', action='store_true', help='Enable debug logging')
    parser.add_argument('--filter-off', action='store_true', help='Disable room filtering')
    parser.add_argument('--keyword', '-k', action='append', help='Add filter keywords (can be used multiple times)')
    args = parser.parse_args()
    
    # 디버그 모드 설정
    if args.debug:
        logging.getLogger("baccarat_client").setLevel(logging.DEBUG)
        logger.info("디버그 모드가 활성화되었습니다.")
    else:
        # 디버그 모드가 아닌 경우 로그 레벨 조정
        logging.getLogger("baccarat_client").setLevel(logging.INFO)
        logging.getLogger("websockets").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    # 필터링 설정 업데이트
    if args.filter_off:
        logger.info("방 필터링이 비활성화되었습니다. 모든 방의 결과가 표시됩니다.")
        # room_mappings.json의 filter_keywords를 빈 배열로 설정
        try:
            import json  # 추가: json 모듈 임포트
            if os.path.exists("room_mappings.json"):
                with open("room_mappings.json", 'r+', encoding='utf-8') as f:
                    mappings_config = json.load(f)
                    mappings_config["filter_keywords"] = []
                    f.seek(0)
                    json.dump(mappings_config, f, indent=4, ensure_ascii=False)
                    f.truncate()
        except Exception as e:
            logger.error(f"필터링 설정 업데이트 중 오류: {e}")
    
    # 명령줄에서 추가 키워드 지정
    if args.keyword:
        try:
            import json  # 추가: json 모듈 임포트
            if os.path.exists("room_mappings.json"):
                with open("room_mappings.json", 'r+', encoding='utf-8') as f:
                    mappings_config = json.load(f)
                    # 기존 키워드에 추가
                    current_keywords = set(mappings_config.get("filter_keywords", []))
                    for keyword in args.keyword:
                        current_keywords.add(keyword)
                    mappings_config["filter_keywords"] = list(current_keywords)
                    
                    # 파일 업데이트
                    f.seek(0)
                    json.dump(mappings_config, f, indent=4, ensure_ascii=False)
                    f.truncate()
                    
                    logger.info(f"필터 키워드 업데이트: {', '.join(mappings_config['filter_keywords'])}")
        except Exception as e:
            logger.error(f"키워드 추가 중 오류: {e}")
    
    # 설정 파일 로드
    config = load_config(args.config)
    
    # 클라이언트 실행
    try:
        await run_client(config)
    except Exception as e:
        logger.error(f"클라이언트 실행 중 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        # ASCII 아트로 시작 메시지 출력
        print("""
    ┌─────────────────────────────────────────────┐
    │         바카라 로비 데이터 수신기          │
    │       Baccarat Lobby Data Receiver         │
    └─────────────────────────────────────────────┘
        """)
        
        # 메인 함수 실행
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n프로그램이 사용자에 의해 종료되었습니다.")
        sys.exit(0)