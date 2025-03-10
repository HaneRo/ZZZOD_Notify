import time
from datetime import datetime
import subprocess
import os
import notify

interval = 4*60*60
Scheduler=os.path.join(os.getcwd(), "OneDragon Scheduler.exe")

import ctypes
import sys

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not is_admin():
    # 重新以管理员权限运行脚本
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit(0)


def task():
    """在此处定义需要定期执行的函数"""
    print(f"执行任务 | 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    subprocess.Popen(Scheduler)
    notify.main()
                



def main():

    print(f"启动定时任务，每 {interval} 秒执行一次...")
    try:
        while True:
            start_time = time.time()
            task()
            execution_time = time.time() - start_time
            sleep_time = max(interval - execution_time, 0)
            time.sleep(sleep_time)
    except KeyboardInterrupt:
        print("\n定时任务已停止")

if __name__ == "__main__":
    main()