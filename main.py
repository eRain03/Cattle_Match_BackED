import uuid
import time
from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 引入本地模块
from models import FarmerCreate, BuyerCreate
from db import db
from matcher import scan_for_matches
from auth import get_password_hash, verify_password, create_access_token, get_current_user

app = FastAPI(title="Cattle Match System (Secured)")

# --- CORS 配置 ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Auth 用户模型 ---
class UserRegister(BaseModel):
    username: str
    password: str

@app.get("/")
def read_root():
    return {"status": "System Operational", "mode": "JSON-DB Auth"}

# =======================
# 1. 认证模块 (Auth)
# =======================

@app.post("/auth/register")
def register(user: UserRegister):
    users = db.load("users.json")
    if any(u['username'] == user.username for u in users):
        raise HTTPException(status_code=400, detail="Username already exists")
    
    hashed_password = get_password_hash(user.password)
    new_user = {"username": user.username, "password": hashed_password}
    db.add_record("users.json", new_user)
    return {"msg": "User created successfully"}

@app.post("/auth/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    users = db.load("users.json")
    user = next((u for u in users if u['username'] == form_data.username), None)
    
    if not user or not verify_password(form_data.password, user['password']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user['username']})
    return {"access_token": access_token, "token_type": "bearer"}

# =======================
# 2. 业务模块 (需鉴权)
# =======================

# 获取我的通知
@app.get("/api/notifications")
def get_my_notifications(current_user: str = Depends(get_current_user)):
    all_notifs = db.load("notifications.json")
    # 筛选属于当前用户的通知
    my_notifs = [n for n in all_notifs if n['user_id'] == current_user]
    # 按时间倒序
    return sorted(my_notifs, key=lambda x: x['timestamp'], reverse=True)

# Farmer 提交
@app.post("/api/farmer")
def create_farmer(data: FarmerCreate, current_user: str = Depends(get_current_user)):
    record = data.dict()
    record['id'] = str(uuid.uuid4())
    record['timestamp'] = time.time()
    record['owner_id'] = current_user # ✅ 绑定当前登录用户
    
    db.add_record("farmers.json", record)
    # 触发匹配逻辑
    count = scan_for_matches(record, "buyers.json", is_new_record_farmer=True)
    return {"id": record['id'], "matches_found": count}

# Buyer 提交
@app.post("/api/buyer")
def create_buyer(data: BuyerCreate, current_user: str = Depends(get_current_user)):
    record = data.dict()
    record['id'] = str(uuid.uuid4())
    record['timestamp'] = time.time()
    record['owner_id'] = current_user # ✅ 绑定当前登录用户
    
    db.add_record("buyers.json", record)
    # 触发匹配逻辑
    count = scan_for_matches(record, "farmers.json", is_new_record_farmer=False)
    return {"id": record['id'], "matches_found": count}

# =======================
# 3. 调试模块 (Debug)
# =======================

@app.get("/api/debug/farmers")
def get_all_farmers():
    return db.load("farmers.json")

@app.get("/api/debug/buyers")
def get_all_buyers():
    return db.load("buyers.json")

@app.get("/api/debug/reset")
def reset_db():
    import os
    try:
        if os.path.exists("data/farmers.json"): os.remove("data/farmers.json")
        if os.path.exists("data/buyers.json"): os.remove("data/buyers.json")
        if os.path.exists("data/notifications.json"): os.remove("data/notifications.json") # 顺便清理通知
        return {"msg": "Database reset successful"}
    except Exception as e:
        return {"msg": str(e)}
