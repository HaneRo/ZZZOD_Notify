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
    items,push_config = notify.load_config("notify.yaml")
    check_interval = 60  # 初始检测间隔
    max_interval = 300   # 最大检测间隔

    notify.logging.info("进程监控启动")
    while True:
        try:
            # 动态调整检测间隔
            time.sleep(check_interval)
            check_interval = min(check_interval * 1.5, max_interval)
            if not notify.is_process_running("OneDragon Scheduler.exe") and not notify.is_process_running("ZenlessZoneZero.exe"):
                notify.logging.warning("目标进程未运行，开始处理日志")
                
                logs = notify.read_log_files([".log/log.txt"])
                if not logs:
                    raise ValueError("最近3小时内未找到有效日志")
                
                results = notify.process_instructions(items, logs)
                message = notify.format_message(results)
                
                notify.logging.info("处理结果：\n%s", message)
                notify.send_notification(message, push_config)
                
                notify.logging.info("程序正常退出")
                break

        except KeyboardInterrupt:
            notify.logging.info("用户手动终止监控")
            sys.exit(0)
        except Exception as e:
            notify.logging.exception("发生未处理异常")
            notify.send_notification(f"⚠️ 监控程序异常：{str(e)}", push_config)
            sys.exit(1)


def main():
    notify.init_logging()
    notify.logging.info(f"启动定时任务，每 {interval} 秒执行一次...")
    try:
        while True:
            start_time = time.time()
            task()
            execution_time = time.time() - start_time
            sleep_time = max(interval - execution_time, 0)
            time.sleep(sleep_time)
    except KeyboardInterrupt:
        notify.logging.info("\n定时任务已停止")

if __name__ == "__main__":
    main()