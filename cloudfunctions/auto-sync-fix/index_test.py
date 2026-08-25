"""V3.0 触发器测试 - 最简版"""
import os
import json
from datetime import datetime


def main_handler(event, context):
    """CloudBase 触发器入口"""
    print(f"=== V3.0 自动同步 {datetime.now().isoformat()} ===")
    print(f"event type: {type(event)}, context type: {type(context)}")
    print(f"cwd: {os.getcwd()}")
    print(f"files: {os.listdir('.')[:10]}")
    print(f"data exists: {os.path.exists('./data')}")
    if os.path.exists('./data'):
        print(f"data files: {os.listdir('./data')}")
    return {"code": 0, "msg": "测试成功"}