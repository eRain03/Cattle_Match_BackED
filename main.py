import uuid
import time
from fastapi.middleware.cors import CORSMiddleware
from models import FarmerCreate, Farmer, BuyerCreate, Buyer
from db import db
from matcher import scan_for_matches
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from auth import get_password_hash, verify_password, create_access_token, get_current_user

app = FastAPI(title="Cattle Match System")

# 允许跨域 (CORS)，否则 Vue 前端无法访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境建议改为前端具体地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 用户模型
class UserRegister(BaseModel):
    username: str
    password: str

# 1. 注册接口
@app.post("/auth/register")
def register(user: UserRegister):
    users = db.load("users.json")
    if any(u['username'] == user.username for u in users):
        raise HTTPException(status_code=400, detail="Username already exists")
    
    hashed_password = get_password_hash(user.password)
    new_user = {"username": user.username, "password": hashed_password}
    db.add_record("users.json", new_user)
    return {"msg": "User created successfully"}

# 2. 登录接口 (返回 Token)
@app.post("/auth/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    users = db.load("users.json")
    user = next((u for u in users if u['username'] == form_data.username), None)
    
    if not user or not verify_password(form_data.password, user['password']):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": user['username']})
    return {"access_token": access_token, "token_type": "bearer"}

# 3. 获取我的通知 (需要 Token)
@app.get("/api/notifications")
def get_my_notifications(current_user: str = Depends(get_current_user)):
    all_notifs = db.load("notifications.json")
    # 筛选属于当前用户的通知
    my_notifs = [n for n in all_notifs if n['user_id'] == current_user]
    # 按时间倒序
    return sorted(my_notifs, key=lambda x: x['timestamp'], reverse=True)

# 4. 修改提交接口，记录 "owner_id"
from models import FarmerCreate, BuyerCreate

@app.post("/api/farmer")
def create_farmer(data: FarmerCreate, current_user: str = Depends(get_current_user)):
    record = data.dict()
    record['id'] = str(uuid.uuid4())
    record['timestamp'] = time.time()
    record['owner_id'] = current_user # ✅ 绑定用户
    
    db.add_record("farmers.json", record)
    count = scan_for_matches(record, "buyers.json", True)
    return {"id": record['id'], "matches_found": count}

@app.post("/api/buyer")
def create_buyer(data: BuyerCreate, current_user: str = Depends(get_current_user)):
    record = data.dict()
    record['id'] = str(uuid.uuid4())
    record['timestamp'] = time.time()
    record['owner_id'] = current_user # ✅ 绑定用户
    
    db.add_record("buyers.json", record)
    count = scan_for_matches(record, "farmers.json", False)
    return {"id": record['id'], "matches_found": count}

@app.get("/api/debug/farmers")
def get_all_farmers():
    """查看所有农场主数据"""
    from db import db
    return db.load("farmers.json")

@app.get("/api/debug/buyers")
def get_all_buyers():
    """查看所有买家数据"""
    from db import db
    return db.load("buyers.json")

@app.get("/api/debug/reset")
def reset_db():
    """(可选) 一键清空数据库，方便重新测试"""
    import os
    try:
        if os.path.exists("data/farmers.json"): os.remove("data/farmers.json")
        if os.path.exists("data/buyers.json"): os.remove("data/buyers.json")
        return {"msg": "Database reset successful"}
    except Exception as e:
        return {"msg": str(e)}


@app.get("/")
def read_root():
    return {"status": "System Operational", "mode": "JSON-DB"}

# --- Farmer 接口 ---
@app.post("/api/farmer")
def create_farmer(data: FarmerCreate):
    # 1. 构造完整记录
    record = data.dict()
    record['id'] = str(uuid.uuid4())
    record['timestamp'] = time.time()
    
    # 2. 存入 farmers.json
    db.add_record("farmers.json", record)
    
    # 3. 触发匹配逻辑：拿着这个 Farmer 去找 Buyers
    match_count = scan_for_matches(record, "buyers.json", is_new_record_farmer=True)
    
    return {
        "msg": "Supply registered successfully", 
        "id": record['id'],
        "matches_found": match_count
    }

# --- Slaughterhouse 接口 ---
@app.post("/api/buyer")
def create_buyer(data: BuyerCreate):
    # 1. 构造完整记录
    record = data.dict()
    record['id'] = str(uuid.uuid4())
    record['timestamp'] = time.time()
    
    # 2. 存入 buyers.json
    db.add_record("buyers.json", record)
    
    # 3. 触发匹配逻辑：拿着这个 Buyer 去找 Farmers
    match_count = scan_for_matches(record, "farmers.json", is_new_record_farmer=False)
    
    return {
        "msg": "Demand request registered", 
        "id": record['id'],
        "matches_found": match_count
    }
