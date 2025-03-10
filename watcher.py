import time
import notify
import time
import logging
import sys
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

notify.init_logging()
items,push_config = notify.load_config("notify.yaml")
check_interval = 60  # 初始检测间隔
max_interval = 300   # 最大检测间隔
previous_status = False  # 记录上一次检测的状态
logging.info("开始检测OneDragon Scheduler")
while True:
    try:
        current_status = notify.is_process_running("OneDragon Scheduler.exe")
        # 当状态从运行变为停止时触发通知
        if previous_status and not current_status:
            logging.info("OneDragon Scheduler已退出，开始检测ZenlessZoneZero")
            while True:
                # 动态调整检测间隔
                time.sleep(check_interval)
                check_interval = min(check_interval * 1.5, max_interval)
                if not notify.is_process_running("OneDragon Scheduler.exe") and not notify.is_process_running("ZenlessZoneZero.exe"):
                        logging.warning("ZenlessZoneZero未运行，开始处理日志")
                        
                        logs = notify.read_log_files([".log/log.txt"])
                        if not logs:
                            raise ValueError("最近3小时内未找到有效日志")
                        
                        results = notify.process_instructions(items, logs)
                        message = notify.format_message(results)
                        
                        logging.info("处理结果：\n%s", message)
                        notify.send_notification(message, push_config)
                        
                        logging.info("继续检测OneDragon Scheduler")
                        break

                
        previous_status = current_status
        time.sleep(5)  # 每5秒检查一次，可调整间隔时间
    except KeyboardInterrupt:
                logging.info("用户手动终止监控")
                sys.exit(0)
    except Exception as e:
                logging.exception("发生未处理异常")
                notify.send_notification(f"⚠️ 监控程序异常：{str(e)}", push_config)
                sys.exit(1)