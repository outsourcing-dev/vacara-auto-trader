import logging
import argparse
import json
import sys
import os
from datetime import datetime

# 상위 디렉토리 모듈 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("session_manager")

def generate_config_template():
    """config.json 템플릿 생성"""
    template = {
        "session_id": "",
        "bare_session_id": "",
        "instance": "",
        "client_version": ""
    }
    
    try:
        # 파일이 이미 존재하는지 확인
        if os.path.exists('config.json'):
            response = input("config.json 파일이 이미 존재합니다. 덮어쓰시겠습니까? (y/n): ")
            if response.lower() != 'y':
                logger.info("템플릿 생성이 취소되었습니다.")
                return
        
        with open('config.json', 'w') as f:
            json.dump(template, f, indent=4)
        
        logger.info("config.json 템플릿이 생성되었습니다.")
    except Exception as e:
        logger.error(f"템플릿 생성 중 오류 발생: {e}")

def update_config():
    """세션 정보 수동 업데이트"""
    try:
        # 기존 설정 파일 로드
        config = {}
        if os.path.exists('config.json'):
            with open('config.json', 'r') as f:
                config = json.load(f)
        
        # 새 세션 정보 입력 받기
        print("\n===== 세션 정보 업데이트 =====")
        print("(입력하지 않으면 기존 값 유지)")
        
        session_id = input(f"session_id [{config.get('session_id', '')}]: ")
        bare_session_id = input(f"bare_session_id [{config.get('bare_session_id', '')}]: ")
        instance = input(f"instance [{config.get('instance', '')}]: ")
        client_version = input(f"client_version [{config.get('client_version', '')}]: ")
        
        # 입력된 값만 업데이트
        if session_id:
            config['session_id'] = session_id
        if bare_session_id:
            config['bare_session_id'] = bare_session_id
        if instance:
            config['instance'] = instance
        if client_version:
            config['client_version'] = client_version
        
        # 변경사항 저장
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=4)
        
        logger.info("세션 정보가 업데이트되었습니다.")
        print("\n현재 설정:")
        for key, value in config.items():
            print(f"  {key}: {value}")
        
        print("\n중요: WebSocket 연결을 위해서는 'session_id'가 유효한 브라우저 세션이어야 합니다.")
        print("브라우저에서 로그인한 후 개발자 도구를 통해 최신 세션 ID를 얻어 업데이트하세요.")
        print("세션이 만료되면 403 Forbidden 에러가 발생할 수 있습니다.")
            
    except Exception as e:
        logger.error(f"설정 업데이트 중 오류 발생: {e}")

def main():
    """세션 관리 도구 메인 함수"""
    parser = argparse.ArgumentParser(description='바카라 세션 관리 도구')
    parser.add_argument('--template', '-t', action='store_true', help='config.json 템플릿 생성')
    parser.add_argument('--update', '-u', action='store_true', help='세션 정보 업데이트')
    
    args = parser.parse_args()
    
    if args.template:
        generate_config_template()
    elif args.update:
        update_config()
    else:
        parser.print_help()

if __name__ == "__main__":
    print("""
┌─────────────────────────────────────────────┐
│           바카라 세션 관리 도구             │
│         Baccarat Session Manager           │
└─────────────────────────────────────────────┘
    """)
    
    main()