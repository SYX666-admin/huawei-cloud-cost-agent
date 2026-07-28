"""
华为云模拟账单数据生成脚本
生成包含 30 天、5 个实例的模拟账单 CSV 文件，保存到 demo 文件夹。
"""

import csv
import os
import random
from datetime import datetime, timedelta


# ==================== 模拟数据配置 ====================

# 5 个模拟实例的基础信息
INSTANCES = [
    {
        "资源ID": "ecs-hw-001",
        "产品类型": "弹性云服务器 ECS",
        "规格": "s6.small.1 | 1vCPU | 1GB",
        "区域": "华北-北京四",
        "用量单位": "小时",
    },
    {
        "资源ID": "ecs-hw-002",
        "产品类型": "弹性云服务器 ECS",
        "规格": "s6.large.2 | 2vCPU | 4GB",
        "区域": "华东-上海一",
        "用量单位": "小时",
    },
    {
        "资源ID": "rds-hw-003",
        "产品类型": "云数据库 RDS",
        "规格": "MySQL 5.7 | 2核4GB | 100GB SSD",
        "区域": "华南-广州",
        "用量单位": "小时",
    },
    {
        "资源ID": "evs-hw-004",
        "产品类型": "云硬盘 EVS",
        "规格": "高IO | 500GB",
        "区域": "华北-北京四",
        "用量单位": "GB",
    },
    {
        "资源ID": "eip-hw-005",
        "产品类型": "弹性公网IP",
        "规格": "独享带宽 | 10Mbps",
        "区域": "华东-上海一",
        "用量单位": "Mbps",
    },
]

# 模拟天数
DAYS = 30

# 各产品类型的费用单价范围（元/单位）
PRICE_RANGE = {
    "弹性云服务器 ECS": (0.5, 2.0),
    "云数据库 RDS": (1.0, 3.5),
    "云硬盘 EVS": (0.3, 0.8),
    "弹性公网IP": (0.1, 0.5),
}

# 各产品类型的每日用量范围
USAGE_RANGE = {
    "弹性云服务器 ECS": (20, 24),       # 小时
    "云数据库 RDS": (20, 24),           # 小时
    "云硬盘 EVS": (300, 500),           # GB
    "弹性公网IP": (5, 10),              # Mbps
}


def generate_daily_records(instance, date_str):
    """
    为单个实例生成某一天的使用记录。
    每天生成 1~3 条记录，模拟不同时段的使用情况。

    参数:
        instance: 实例信息字典
        date_str: 日期字符串，格式 YYYY-MM-DD

    返回:
        记录列表，每条记录为一个字典
    """
    records = []
    product_type = instance["产品类型"]
    record_count = random.randint(1, 3)  # 每天随机 1~3 条记录

    for _ in range(record_count):
        # 随机生成使用时长（小时），保留 1 位小数
        usage_hours = round(random.uniform(0.5, 24.0), 1)

        # 根据产品类型确定用量范围并随机生成用量
        usage_min, usage_max = USAGE_RANGE.get(product_type, (1, 10))
        
        # 特殊处理闲置资源
        if instance["资源ID"] == "eip-hw-005":
            # EIP 用量为0，费用100元/月，平均到每天约3.33元
            usage = 0.0
            cost = 3.33
        elif instance["资源ID"] == "ecs-hw-002":
            # ECS 用量极低，费用200元/月，平均到每天约6.67元
            usage = round(random.uniform(0.5, 5.0), 2)
            cost = 6.67
        else:
            # 正常资源
            usage = round(random.uniform(usage_min, usage_max), 2)
            # 根据产品类型确定单价范围并计算费用
            price_min, price_max = PRICE_RANGE.get(product_type, (0.1, 1.0))
            unit_price = round(random.uniform(price_min, price_max), 4)
            cost = round(usage * unit_price, 2)

        records.append({
            "日期": date_str,
            "产品类型": product_type,
            "规格": instance["规格"],
            "区域": instance["区域"],
            "资源ID": instance["资源ID"],
            "使用时长": usage_hours,
            "费用": cost,
            "用量": usage,
            "用量单位": instance["用量单位"],
        })

    return records


def generate_bill_data():
    """
    生成完整的 30 天模拟账单数据。

    返回:
        所有账单记录的列表
    """
    all_records = []
    start_date = datetime.now() - timedelta(days=DAYS)

    for day_offset in range(DAYS):
        current_date = start_date + timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")

        for instance in INSTANCES:
            daily_records = generate_daily_records(instance, date_str)
            all_records.extend(daily_records)

    return all_records


def save_to_csv(records, output_path):
    """
    将账单记录保存为 CSV 文件。

    参数:
        records: 账单记录列表
        output_path: 输出文件路径
    """
    # 定义 CSV 列顺序
    fieldnames = ["日期", "产品类型", "规格", "区域", "资源ID", "使用时长", "费用", "用量", "用量单位"]

    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"模拟账单已生成，共 {len(records)} 条记录，保存至: {output_path}")


def main():
    """主函数：生成模拟账单并保存到 demo 文件夹。"""
    # 获取项目根目录（backend 的上级目录）
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_path = os.path.join(base_dir, "demo", "sample_bill.csv")

    # 设置随机种子，保证每次生成结果可复现
    random.seed(42)

    records = generate_bill_data()
    save_to_csv(records, output_path)


if __name__ == "__main__":
    main()
