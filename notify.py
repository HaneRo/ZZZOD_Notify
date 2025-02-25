import psutil
import time
import re
import yaml
import os
import httpx
import logging
import sys
from dataclasses import dataclass
from typing import List, Dict, Any

# 配置数据类
@dataclass
class AppConfig:
    allowed: List[str]
    bot_token: str
    chat_id: str
    proxy: str

# 日志初始化
def init_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("monitor.log", encoding="utf-8")
        ]
    )

# 进程检测
def is_process_running(process_name: str) -> bool:
    """优化后的进程检测函数"""
    return any(
        proc.info["name"] == process_name
        for proc in psutil.process_iter(["name"])
    )

# 配置加载
def load_config(yaml_path: str) -> AppConfig:
    """加载应用配置"""
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            notify_cfg = config["notify"]
            return AppConfig(
                allowed=[str(item) for item in notify_cfg["list"]],
                bot_token=notify_cfg["bot_token"],
                chat_id=notify_cfg["chat_id"],
                proxy=notify_cfg["proxy"]
            )
    except (FileNotFoundError, yaml.YAMLError) as e:
        logging.error(f"配置加载失败: {str(e)}")
        sys.exit(1)

# 通知发送
def send_notification(message: str, config: AppConfig) -> None:
    """带错误处理的通知发送"""
    proxies = {
        "http://": config.proxy,
        "https://": config.proxy,
    }
    
    try:
        with httpx.Client(proxies=proxies, timeout=10) as client:
            response = client.post(
                f"https://api.telegram.org/bot{config.bot_token}/sendMessage",
                json={
                    "chat_id": config.chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }
            )
            response.raise_for_status()
            logging.info("通知发送成功")
    except httpx.HTTPError as e:
        logging.error(f"HTTP错误: {str(e)}")
    except Exception as e:
        logging.error(f"通知发送失败: {str(e)}")

# 日志读取
def read_log_files(log_paths: List[str]) -> str:
    """智能日志读取"""
    combined = []
    for path in log_paths:
        try:
            if not os.path.exists(path):
                logging.warning(f"日志文件不存在: {path}")
                continue

            with open(path, "r", encoding="utf-8") as f:
                # 使用生成器表达式处理大文件
                combined.extend(line.strip() for line in f if line.strip())
        except UnicodeDecodeError:
            logging.error(f"文件编码错误: {path}")
        except Exception as e:
            logging.error(f"日志读取异常: {str(e)}")
    
    return "\n".join(combined) if combined else ""

# 日志处理
def process_instructions(allowed_instructions: List[str], log_text: str) -> List[Dict[str, Any]]:
    """优化后的日志处理"""
    # 预编译正则表达式
    instr_pattern = re.compile(
        r"^.*指令\s*\[\s*({})\s*\]\s*执行\s*(\S+)".format(
            "|".join(fr"\s*{re.escape(i)}\s*" for i in allowed_instructions)
        ),
        re.IGNORECASE
    )

    instruction_states = {
        instr: {"is_success": False, "states": []}
        for instr in allowed_instructions
    }

    for line in log_text.split("\n"):
        if not line:
            continue

        match = instr_pattern.search(line)
        if match:
            raw_instr = match.group(1).strip()
            status = match.group(2).upper()

            # 匹配允许的指令（保留大小写）
            matched_instr = next(
                (instr for instr in allowed_instructions
                 if raw_instr.lower() == instr.lower()),
                None
            )

            if not matched_instr:
                continue

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
    """生成格式化消息"""
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
        parts.append(f"，全部失败❌")
    return "\n".join(parts) if parts else "⚠️ 未检测到有效指令状态"

# 主程序
def main():
    init_logging()
    config = load_config("notify.yaml")
    check_interval = 60  # 初始检测间隔
    max_interval = 300   # 最大检测间隔

    logging.info("进程监控启动")

    while True:
        try:
            if not is_process_running("OneDragon Scheduler.exe"):
                logging.warning("目标进程未运行，开始处理日志")
                
                logs = read_log_files([".log/log.txt"])
                if not logs:
                    raise ValueError("未找到有效日志内容")

                results = process_instructions(config.allowed, logs)
                message = format_message(results)
                
                logging.info("处理结果：\n%s", message)
                send_notification(message, config)
                
                logging.info("程序正常退出")
                sys.exit(0)

            # 动态调整检测间隔
            check_interval = min(check_interval * 1.5, max_interval)
            time.sleep(check_interval)

        except KeyboardInterrupt:
            logging.info("用户手动终止监控")
            sys.exit(0)
        except Exception as e:
            logging.exception("发生未处理异常")
            send_notification(f"⚠️ 监控程序异常：{str(e)}", config)
            sys.exit(1)

if __name__ == "__main__":
    main()