import time
from typing import Dict
from db import db

# ✅ 升级：支持存储详细数据 (details)
def save_notification(user_id: str, title: str, details: Dict):
    notif = {
        "user_id": user_id,
        "message": title,     # 简短标题
        "details": details,   # 详细匹配数据 (对方是谁，电话多少，什么货)
        "timestamp": time.time(),
        "read": False
    }
    db.add_record("notifications.json", notif)
    print(f"🔔 Notification saved for {user_id}")

def check_match(farmer: Dict, buyer: Dict) -> bool:
    """
判断 Farmer 和 Buyer 是否匹配
支持：州+城市 的精确/模糊匹配
"""

    # 1. 地理位置匹配 (核心逻辑升级)
    # Buyer 的 targets 是一个列表，例如: [{'state': 'PA', 'city': 'ANY'}, {'state': 'SP', 'city': 'Campinas'}]
    location_match = False
    buyer_targets = buyer.get('targets', [])

    farmer_state = farmer.get('state')
    farmer_city = farmer.get('city')

    for target in buyer_targets:
        # 先对州
        if target['state'] == farmer_state:
            # 再对城市：如果是 "ANY" 或者 城市名完全一致，则匹配
            if target['city'] == 'ANY' or target['city'] == farmer_city:
                location_match = True
                break

    if not location_match:
        return False

    # 2. 品种匹配
    if buyer.get('race') != "Any" and buyer.get('race') != farmer.get('race'):
        return False

    # 3. 年龄匹配
    buyer_min = buyer.get('ageMin') or 0
    buyer_max = buyer.get('ageMax') or 100
    if not (buyer_min <= farmer.get('age', 0) <= buyer_max):
        return False

    return True

def scan_for_matches(new_record: Dict, target_db_name: str, is_new_record_farmer: bool):
    targets = db.load(target_db_name)
    matches = []
    
    for target in targets:
        farmer = new_record if is_new_record_farmer else target
        buyer = target if is_new_record_farmer else new_record
        
        if check_match(farmer, buyer):
            matches.append(target)
            
            # --- 构造详细的通知数据 ---
            
            # 1. 通知新提交者 (例如我刚发了需求，匹配到了现有的供应)
            if 'owner_id' in new_record:
                save_notification(
                    user_id=new_record['owner_id'],
                    title="Match Found: New Deal Available!",
                    details={
                        "role": "You matched with a " + ("Buyer" if is_new_record_farmer else "Farmer"),
                        "contact": target.get('contact'),
                        "race": target.get('race'),
                        "qty": target.get('quantity'),
                        "location": target.get('location')
                    }
                )
            
            # 2. 通知旧数据的拥有者 (例如我以前发的供应，被新需求匹配了)
            if 'owner_id' in target:
                save_notification(
                    user_id=target['owner_id'],
                    title="New Interest in your Listing!",
                    details={
                        "role": "New " + ("Farmer" if not is_new_record_farmer else "Buyer") + " matched you",
                        "contact": new_record.get('contact'),
                        "race": new_record.get('race'),
                        "qty": new_record.get('quantity'),
                        "location": new_record.get('location')
                    }
                )
            
    return len(matches)
