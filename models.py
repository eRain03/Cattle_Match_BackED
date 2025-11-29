from pydantic import BaseModel
from typing import List, Optional

# Farmer 提交的数据结构
class FarmerCreate(BaseModel):
    race: str
    age: int
    sex: str
    quantity: int
    location: str  # 例如 "SP"
    contact: str

# 存入数据库的结构（多一个 ID 和 时间）
class Farmer(FarmerCreate):
    id: str
    timestamp: float

# Slaughterhouse 提交的数据结构
class BuyerCreate(BaseModel):
    location: List[str] # 例如 ["SP", "MG"]
    race: str           # "Nelore" 或 "Any"
    ageMin: Optional[int] = 0
    ageMax: Optional[int] = 100
    sex: str            # "Male", "Female", "Any"
    quantity: int       # 最小需求量
    contact: str

# 存入数据库的结构
class Buyer(BuyerCreate):
    id: str
    timestamp: float