import uuid
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models import FarmerCreate, Farmer, BuyerCreate, Buyer
from db import db
from matcher import scan_for_matches

app = FastAPI(title="Cattle Match System")

# 允许跨域 (CORS)，否则 Vue 前端无法访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境建议改为前端具体地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
