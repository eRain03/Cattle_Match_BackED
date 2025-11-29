import time
from typing import Dict
from db import db

# ✅ 1. 定义保存通知的函数
def save_notification(user_id: str, message: str):
    """将通知写入 notifications.json"""
    notif = {
        "user_id": user_id,
        "message": message,
        "timestamp": time.time(),
        "read": False
    }
    db.add_record("notifications.json", notif)
    print(f"🔔 Notification saved for {user_id}")

# ✅ 2. 核心匹配逻辑 (保留之前的业务规则)
def check_match(farmer: Dict, buyer: Dict) -> bool:
    """
    判断 Farmer 和 Buyer 是否匹配
    """
    # 1. 地理位置匹配 (Buyer location 是列表)
    # 注意：前端传来的可能是简写 'SP'，也可能是对象，但在 API 层我们已经处理成字符串了
    if farmer.get('location') not in buyer.get('location', []):
        return False

    # 2. 品种匹配
    if buyer.get('race') != "Any" and buyer.get('race') != farmer.get('race'):
        return False

    # 3. 年龄匹配 (范围)
    buyer_min = buyer.get('ageMin') or 0
    buyer_max = buyer.get('ageMax') or 100
    if not (buyer_min <= farmer.get('age', 0) <= buyer_max):
        return False
        
    # 4. 数量匹配 (简单判断)
    # if farmer.get('quantity', 0) < buyer.get('quantity', 0):
    #    return False

    return True

# ✅ 3. 扫描匹配并发送通知
def scan_for_matches(new_record: Dict, target_db_name: str, is_new_record_farmer: bool):
    """
    扫描数据库，找到匹配项后，给双方发送通知
    """
    targets = db.load(target_db_name)
    matches = []
    
    for target in targets:
        # 确定谁是 Farmer 谁是 Buyer，以便传入 check_match
        farmer = new_record if is_new_record_farmer else target
        buyer = target if is_new_record_farmer else new_record
        
        if check_match(farmer, buyer):
            matches.append(target)
            
            # --- 关键修正：使用 save_notification ---
            
            # 1. 通知新提交者 (如果他有 owner_id)
            if 'owner_id' in new_record:
                msg = f"Match found! Contact: {target.get('contact')}"
                save_notification(new_record['owner_id'], msg)
            
            # 2. 通知旧数据的拥有者 (如果他有 owner_id)
            if 'owner_id' in target:
                msg = f"New match found! Contact: {new_record.get('contact')}"
                save_notification(target['owner_id'], msg)
            
    return len(matches)
