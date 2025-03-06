import psutil
import time
import re
import yaml
import os
import logging
import sys
from typing import List, Dict, Any
from datetime import datetime, timedelta
import push

# 日志初始化
def init_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(".log","notify.log"), encoding="utf-8")
        ]
    )

# 进程检测
def is_process_running(process_name: str) -> bool:
    return any(
        proc.info["name"] == process_name
        for proc in psutil.process_iter(["name"])
    )

# 配置加载
def load_config(yaml_path: str):
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            if os.getenv('ZZZOD_notify'):
                notify_cfg = os.getenv('ZZZOD_notify')
            else:
                notify_cfg = config["list"]
            for k in push.push_config:
                if os.getenv(k):
                    push.push_config[k] = os.getenv(k)
                elif config.get('notify', {}).get(k) is not None:
                    push.push_config[k] = config.get('notify', {}).get(k)
            return [str(item) for item in notify_cfg],push.push_config
    except (FileNotFoundError, yaml.YAMLError) as e:
        logging.error(f"配置加载失败: {str(e)}")
        sys.exit(1)

# 通知发送
def send_notification(message: str, config) -> None:
    try:
        push.send("绝区零一条路运行通知",message,config)
    except Exception as e:
        logging.error(f"通知发送失败: {str(e)}")

def parse_log_time(time_str: str) -> datetime:
    """解析日志时间并处理跨天情况"""
    try:
        log_time = datetime.strptime(time_str, "%H:%M:%S.%f").time()
        now = datetime.now()
        today_date = now.date()
        
        # 组合当前日期和日志时间
        log_datetime = datetime.combine(today_date, log_time)
        
        # 处理跨天情况（如果日志时间晚于当前时间，则视为前一天）
        if log_datetime > now:
            log_datetime -= timedelta(days=1)
            
        return log_datetime
    except ValueError as e:
        raise ValueError(f"无效时间格式: {time_str}") from e

# 日志读取（添加时间过滤）
def read_log_files(log_paths: List[str]) -> str:
    """读取并过滤最近3小时的日志"""
    combined = []
    time_pattern = re.compile(r"^\[(\d{2}:\d{2}:\d{2}\.\d{3})\]")
    three_hours_ago = datetime.now() - timedelta(hours=3)
    
    for path in log_paths:
        try:
            if not os.path.exists(path):
                logging.warning(f"日志文件不存在: {path}")
                continue

            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # 提取时间戳
                    match = time_pattern.match(line)
                    if not match:
                        continue
                    
                    try:
                        log_time = parse_log_time(match.group(1))
                        if log_time >= three_hours_ago:
                            combined.append(line)
                    except Exception as e:
                        logging.warning(f"时间解析失败: {line[:50]}... ({str(e)})")
                        
        except UnicodeDecodeError:
            logging.error(f"文件编码错误: {path}")
        except Exception as e:
            logging.error(f"日志读取异常: {str(e)}")
    
    return "\n".join(combined) if combined else ""

# 日志处理
def process_instructions(allowed_instructions: List[str], log_text: str) -> List[Dict[str, Any]]:
    instr_pattern = re.compile(
        r"指令\s*\[\s*({})\s*\]\s.*执行\s*(\S+)".format(
            "|".join(fr"\s*{re.escape(i)}\s*" for i in allowed_instructions)
        ),
        re.IGNORECASE
    )

    instruction_states = {
        instr: {"is_success": False, "states": []}
        for instr in allowed_instructions
    }

    for line in log_text.split("\n"):
        match = instr_pattern.search(line)
        if match:
            raw_instr = match.group(1).strip()
            status = match.group(2).upper()

            matched_instr = next(
                (instr for instr in allowed_instructions
                 if raw_instr.lower() == instr.lower()),
                None
            )

            if matched_instr:
                record = instruction_states[matched_instr]
                if status == "成功" and not record["is_success"]:
                    record["is_success"] = True
                    record["states"].append(status)
                elif not record["is_success"]:
                    record["states"].append(status)

    return [
        {
            "instruction": instr,
            "is_success": data["is_success"],
            "states": data["states"]
        }
        for instr, data in instruction_states.items()
        if data["states"]
    ]

# 消息格式化
def format_message(results: List[Dict[str, Any]]) -> str:
    success = []
    failure = []

    for item in results:
        if item["is_success"]:
            success.append(item["instruction"])
        else:
            failure.append(item["instruction"])

    parts = [f"OneDragon执行完成："]
    if failure:
        parts.append(f"❌ 失败指令：{', '.join(failure)}")
    else:
        parts.append(f"全部成功✅")
    if success:
        parts.append(f"成功指令：{', '.join(success)}")
    else:
        parts.append(f"全部失败❌")
    return "\n".join(parts) if parts else "⚠️ 未检测到有效指令状态"

# 主程序
def main():
    init_logging()
    items,push_config = load_config("notify.yaml")
    check_interval = 60  # 初始检测间隔
    max_interval = 300   # 最大检测间隔

    logging.info("进程监控启动")
    while True:
        try:
            # 动态调整检测间隔
            time.sleep(check_interval)
            check_interval = min(check_interval * 1.5, max_interval)
            if not is_process_running("OneDragon Scheduler.exe") and not is_process_running("ZenlessZoneZero.exe"):
                logging.warning("目标进程未运行，开始处理日志")
                
                logs = read_log_files([".log/log.txt"])
                if not logs:
                    raise ValueError("最近3小时内未找到有效日志")
                
                results = process_instructions(items, logs)
                message = format_message(results)
                
                logging.info("处理结果：\n%s", message)
                send_notification(message, push_config)
                
                logging.info("程序正常退出")
                sys.exit(0)

        except KeyboardInterrupt:
            logging.info("用户手动终止监控")
            sys.exit(0)
        except Exception as e:
            logging.exception("发生未处理异常")
            send_notification(f"⚠️ 监控程序异常：{str(e)}", push_config)
            sys.exit(1)

if __name__ == "__main__":
    main()