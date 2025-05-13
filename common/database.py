import mysql.connector
from contextlib import contextmanager
from .config import Config

class DatabaseHandler:
    def __init__(self):
        self.config = Config.DB_CONFIG
        self.conn = None
        self.init_db()
        
    def init_db(self):
        """데이터베이스 초기화: hol_user 테이블 생성"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # hol_user 테이블 생성 (없으면)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS hol_user (
                        no INT AUTO_INCREMENT PRIMARY KEY,
                        id VARCHAR(50) UNIQUE NOT NULL,
                        pw VARCHAR(100) NOT NULL,
                        end_date DATE NOT NULL,
                        name VARCHAR(50) DEFAULT NULL,
                        phone VARCHAR(20) DEFAULT NULL,
                        referrer VARCHAR(50) DEFAULT NULL,
                        logged_in TINYINT(4) DEFAULT 0,
                        last_login DATETIME DEFAULT NULL
                    )
                """)

                conn.commit()
                print("데이터베이스(hol_user) 초기화 완료")
        except Exception as e:
            print(f"데이터베이스 초기화 오류: {e}")
    
    @contextmanager
    def get_connection(self):
        """데이터베이스 연결 컨텍스트 매니저"""
        conn = None
        try:
            conn = mysql.connector.connect(**self.config)
            yield conn
        except Exception as e:
            print(f"데이터베이스 연결 오류: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

# 싱글톤 인스턴스
db_handler = DatabaseHandler()
