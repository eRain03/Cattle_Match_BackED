from typing import List, Dict
import time
from db import db

def save_notification(user_id: str, message: str):
    notification = {
        "user_id": user_id,
        "message": message,
        "read": False,
        "timestamp": time.time()
    }
    # 写入 notifications.json
    db.add_record("notifications.json", notification)
    print(f"🔔 Notification saved for {user_id}: {message}")

def scan_for_matches(new_record: dict, target_db_name: str, is_new_record_farmer: bool):
    targets = db.load(target_db_name)
    matches = []
    
    for target in targets:
        # 假设这里调用之前的 check_match 逻辑 (略)
        # 为了演示，我们假设只要有数据就匹配
        # 在实际代码中保留你的 check_match 函数
        from matcher import check_match # 引用回自身或确保在同一文件
        if check_match(new_record, target): 
            matches.append(target)
            
            # ✅ 新逻辑：给双方发送通知
            # 注意：这要求 Farmer/Buyer 数据里必须包含 'owner_id'
            
            # 1. 通知新提交者
            if 'owner_id' in new_record:
                save_notification(new_record['owner_id'], f"Match found with contact: {target['contact']}")
            
            # 2. 通知旧数据的拥有者
            if 'owner_id' in target:
                save_notification(target['owner_id'], f"New match found! Contact: {new_record['contact']}")
            
    return len(matches)

def check_match(farmer: Dict, buyer: Dict):
    """
    核心匹配算法
    返回: True/False
    """
    # 1. 地理位置匹配 (Buyer 的 location 是列表，Farmer 是单值)
    if farmer['location'] not in buyer['location']:
        return False

    # 2. 品种匹配 (Buyer 可能是 "Any")
    if buyer['race'] != "Any" and buyer['race'] != farmer['race']:
        return False

    # 3. 性别匹配
    # 前端传来的可能是 "Male (Bull)"，我们简单判断包含关系或者完全匹配
    # 这里做简化处理，假设前端传的值是标准的
    if buyer['sex'] != "Any" and buyer['sex'] not in farmer['sex']: 
        return False

    # 4. 年龄匹配 (范围)
    if not (buyer['ageMin'] <= farmer['age'] <= buyer['ageMax']):
        return False

    # 5. 数量匹配 (Farmer 供货量是否满足 Buyer 最小需求?)
    # 商业逻辑：有时即使不够也能聊，但这里我们设定硬性门槛
    if farmer['quantity'] < buyer['quantity']:
        return False

    return True

def scan_for_matches(new_record: Dict, target_db_name: str, is_new_record_farmer: bool):
    """
    扫描数据库寻找匹配
    """
    from db import db
    targets = db.load(target_db_name)
    
    matches = []
    for target in targets:
        farmer = new_record if is_new_record_farmer else target
        buyer = target if is_new_record_farmer else new_record
        
        if check_match(farmer, buyer):
            matches.append(target)
            send_notification(farmer, buyer, "100% Match")
            
    return len(matches)
