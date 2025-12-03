import uuid
import time
from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from mailer import send_contact_info_email
# 引入 matcher 里的 save_notification 来发站内信
from matcher import save_notification

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


@app.get("/api/market")
def get_market_data():
    """获取所有供需数据，按时间倒序排列"""
    # 1. 读取数据
    all_farmers = db.load("farmers.json")
    all_buyers = db.load("buyers.json")

    # 2. 简单的隐私处理：为了演示，市场列表暂不隐藏联系方式
    # 实际生产中，这里通常会把 contact 字段设为 "***" 或隐藏

    # 3. 排序 (最新的在前面)
    all_farmers.sort(key=lambda x: x['timestamp'], reverse=True)
    all_buyers.sort(key=lambda x: x['timestamp'], reverse=True)

    return {
        "supply": all_farmers,
        "demand": all_buyers
    }


# =======================
# 1. 认证模块 (Auth)
# =======================

@app.get("/api/my-listings")
def get_my_listings(current_user: str = Depends(get_current_user)):
    # 1. 读取两个库
    all_farmers = db.load("farmers.json")
    all_buyers = db.load("buyers.json")
    
    # 2. 筛选属于当前用户的
    my_supply = [f for f in all_farmers if f.get('owner_id') == current_user]
    my_demand = [b for b in all_buyers if b.get('owner_id') == current_user]
    
    # 3. 按时间倒序排列
    my_supply.sort(key=lambda x: x['timestamp'], reverse=True)
    my_demand.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return {
        "supply": my_supply,  # 我是 Farmer 卖出的
        "demand": my_demand   # 我是 Buyer 想买的
    }


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

class UnlockRequest(BaseModel):
    listing_id: str
    listing_type: str # 'supply' 或 'demand'
    target_email: str # 用户填写的接收邮箱

@app.post("/api/market/unlock")
def unlock_listing(req: UnlockRequest, current_user: str = Depends(get_current_user)):
    """
付费解锁接口：
1. 找到该 Listing
2. 发邮件给请求者 (req.target_email)
3. 发站内信给请求者 (current_user)
    """
    # 1. 查找 Listing
    db_file = "farmers.json" if req.listing_type == 'supply' else "buyers.json"
    listings = db.load(db_file)
    target_item = next((item for item in listings if item['id'] == req.listing_id), None)

    if not target_item:
        raise HTTPException(status_code=404, detail="Listing not found")

    # 2. 准备数据
    info = {
        "type": req.listing_type.upper(),
        "race": target_item.get('race'),
        "location": target_item.get('city', 'Unknown') if req.listing_type == 'supply' else "Multiple Regions",
        "contact": target_item.get('contact')
    }

    # 3. 发送邮件给购买者
    send_contact_info_email(req.target_email, info)

    # 4. 发送站内信给购买者
    save_notification(
        user_id=current_user,
        title=f"Unlocked: {info['race']}",
        details=info # 这样用户在站内信里也能看到解锁后的电话
    )

    return {"status": "success", "msg": "Contact details sent to your email."}
