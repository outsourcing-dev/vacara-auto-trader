# holdem-auto-trader/common/config.py
class Config:
    # 데이터베이스 설정
    DB_CONFIG = {
        'host': 'svc.sel4.cloudtype.app',
        'port': 30351,
        'user': 'root',
        'password': 'qw4646',
        'database': 'manager',
        'charset': 'utf8mb4',
        'collation': 'utf8mb4_general_ci'
    }
    
    # JWT 설정
    SECRET_KEY = "your-secret-key-here"  # 실제 배포 시 환경변수로 관리
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24시간
    
    # 앱 설정
    APP_NAME = "Vacara Auto Trader"
    ADMIN_USERNAME = "eropoo1"  # 초기 관리자 계정
    ADMIN_PASSWORD = "464646"  # 초기 비밀번호 (실제로는 해싱 처리)