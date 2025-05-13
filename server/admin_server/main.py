import os
import sys
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import timedelta

# 상위 디렉토리 모듈 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.database import db_handler
from common.security import verify_password, create_access_token, decode_token
from common.config import Config

# FastAPI 앱 생성
app = FastAPI(title="Vacara Auto Trader Admin")

# 템플릿 및 정적 파일 설정
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# OAuth2 설정
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# 하드코딩 관리자 정보
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1234"

# 사용자 인증 유틸리티
async def get_current_user(token: str = Depends(oauth2_scheme)):
    """현재 로그인된 사용자 정보 가져오기"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증에 실패했습니다",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception
    
    username = payload.get("sub")
    if username is None:
        raise credentials_exception
    
    return {"username": username}

# 루트 리다이렉트
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return RedirectResponse(url="/login")

# 로그인 페이지
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# 로그인 처리
@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username != ADMIN_USERNAME or form_data.password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=Config.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": ADMIN_USERNAME},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

# 대시보드 페이지
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

# 사용자 모델들
class UserCreate(BaseModel):
    id: str
    pw: str
    end_date: str
    name: str = ''
    phone: str = ''
    referrer: str = ''

class UserUpdate(BaseModel):
    pw: str
    end_date: str
    name: str = ''
    phone: str = ''
    referrer: str = ''

# 사용자 목록 조회
@app.get("/api/users")
async def get_users():
    with db_handler.get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                no,
                id,
                pw,
                end_date,
                name,
                phone,
                referrer,
                logged_in,
                last_login
            FROM hol_user
            ORDER BY no DESC
        """)
        users = cursor.fetchall()
    
    return {"users": users}

# 사용자 추가
@app.post("/api/users")
async def create_user(user: UserCreate):
    with db_handler.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO hol_user (id, pw, end_date, name, phone, referrer)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user.id, user.pw, user.end_date, user.name, user.phone, user.referrer))
        conn.commit()
    
    return {"message": "사용자 추가 완료"}

# 사용자 수정
@app.put("/api/users/{user_id}")
async def update_user(user_id: str, user: UserUpdate):
    with db_handler.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE hol_user
            SET pw = %s, end_date = %s, name = %s, phone = %s, referrer = %s
            WHERE id = %s
        """, (user.pw, user.end_date, user.name, user.phone, user.referrer, user_id))
        conn.commit()
    
    return {"message": "사용자 수정 완료"}

# 사용자 삭제
@app.delete("/api/users/{user_id}")
async def delete_user(user_id: str):
    with db_handler.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM hol_user WHERE id = %s", (user_id,))
        conn.commit()
    
    return {"message": "사용자 삭제 완료"}

@app.get("/api/statistics")
async def get_statistics():
    """대충 통계값 더미 데이터 리턴"""
    return {
        "active_users": 10,
        "total_sessions": 20,
        "active_sessions": 5,
        "total_profit": 1000000
    }


# 애플리케이션 실행
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
