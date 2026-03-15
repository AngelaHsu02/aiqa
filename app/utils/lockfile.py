import os
import pickle
from datetime import datetime, timedelta

LOCK_TIMEOUT_SECONDS = 4*60*60  # 正式版可調成 4*60*60 (即 4 小時)


LOCK_FILE = "lock_holder.pkl"

def if_get_lock(employee_id): #獲取鎖定
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}正在檢查 {employee_id} 是否可獲權限")
    # 如果有鎖讀取
    if os.path.exists(LOCK_FILE):
        with open(LOCK_FILE, "rb") as f:
            lock_info = pickle.load(f)
        lock_holder = lock_info["lock_holder"]
        timestamp_str = lock_info["timestamp"]
        lock_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        now = datetime.now()

        # 超時 → employee_id 拿到鎖
        if now - lock_time > timedelta(seconds=LOCK_TIMEOUT_SECONDS):
            print(f"⚠️ 鎖定已超時 {LOCK_TIMEOUT_SECONDS} 秒， {lock_holder} 被釋放，{employee_id} 取得鎖")
            os.remove(LOCK_FILE)
            set_lock_holder(employee_id)
            return True, employee_id, f"⚠️ 鎖定已超時 {LOCK_TIMEOUT_SECONDS} 秒， {lock_holder} 被釋放，{employee_id} 取得鎖"

        # employee_id不是lock_holder → lock_holder繼續拿鎖
        if lock_holder != employee_id:
            print(f"{employee_id} 嘗試取得鎖，但已由 {lock_holder} 持有")
            return False, lock_holder, None
        # employee_id是lock_holder → employee_id繼續拿鎖
        else:
            print(f"{employee_id} 再次進入")
            return True, employee_id, None

    # 無鎖建立新鎖
    else:
        set_lock_holder(employee_id)
        return True, employee_id, None

def set_lock_holder(employee_id): #建立鎖LOCK_FILE
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}建立鎖檔lock_holder:{employee_id}")
    with open(LOCK_FILE, "wb") as f:
        pickle.dump({"lock_holder": employee_id, "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, f)
    return True

def if_release_lock_holder(current_user):
    if os.path.exists(LOCK_FILE):
        with open(LOCK_FILE, "rb") as f:
            lock_info = pickle.load(f)
        print(f"檢查使用者： {current_user} vs 持鎖者：{lock_info['lock_holder']}")
        if lock_info["lock_holder"] == current_user:
            os.remove(LOCK_FILE)
            print(f"鎖已釋放 by {current_user}")
            return True
        else:
            print(f"無權釋放鎖 by {current_user}")
            return False
    return False
