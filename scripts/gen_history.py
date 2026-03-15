"""
生成 2026-01 / 2026-02 两个月的模拟历史数据。

策略：
- 以 2026-03 真实数据为蓝本，按月往前推日期
- 1月异常率 ~3.8%，2月异常率 ~6.2%，3月真实 ~4.9%  →  "2月恶化、3月回落"故事线
- 供应商、品类、工厂分布保持一致，但权重微调
- 1月生成少量 batch_actions（已完成 / 已关闭），2月多一些
- 正常物料库龄：时间越早 → A类占比越高（货还没老）
"""

import random
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "backend" / "rm_inventory_demo.db"
random.seed(42)

# ── 连接数据库 ──────────────────────────────────────────
conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# ── 读取 3 月全量数据 ──────────────────────────────────
cur.execute("SELECT * FROM rm_inventory_snapshot WHERE snapshot_month = '2026-03'")
rows_mar = [dict(r) for r in cur.fetchall()]
print(f"3月数据: {len(rows_mar)} 条")

# ── 工具函数 ──────────────────────────────────────────

def shift_date(d_str, days):
    """将日期字符串往前推 days 天。"""
    if not d_str:
        return None
    try:
        d = date.fromisoformat(d_str)
        return str(d - timedelta(days=days))
    except (ValueError, TypeError):
        return d_str

def assign_aging(inbound_str, snapshot_date):
    """根据入库日期和快照日期重新计算库龄。"""
    if not inbound_str:
        return "A", "≤30天"
    try:
        inbound = date.fromisoformat(inbound_str)
        days = (snapshot_date - inbound).days
    except (ValueError, TypeError):
        return "A", "≤30天"

    if days <= 30:
        return "A", "≤30天"
    elif days <= 90:
        return "B", "＞30天≤90天"
    elif days <= 180:
        return "C", "＞90天≤180天"
    elif days <= 360:
        return "D", "＞180天≤360天"
    else:
        return "E", "＞360天"

def decide_abnormal_jan(row, rng):
    """1月异常率目标 ~3.8%，比3月低。"""
    if row["quality_flag"] == "N":
        # 3月的异常批次，1月只保留约 70%
        return rng.random() < 0.70
    return False

def decide_abnormal_feb(row, rng):
    """2月异常率目标 ~6.2%，比3月高。"""
    if row["quality_flag"] == "N":
        return True  # 原本异常的全保留
    # 额外把部分正常批次标记为异常（模拟恶化）
    return rng.random() < 0.015  # 1.5% 的正常批次也标异常

ABNORMAL_REASONS_POOL = [
    "不良品,已冻结",
    "不良品",
    "不良品,超期库存(>180天),呆滞原因",
    "不良品,超期库存(>180天)",
    "不良品,呆滞原因",
    "不良品,超期库存(>180天),已冻结",
]

def generate_month(month_str, snapshot_date, day_shift, abnormal_fn, sample_ratio=0.92):
    """
    基于3月数据生成一个月的模拟数据。
    sample_ratio: 随机抽取比例（每月库存略有差异）
    """
    rng = random.Random(hash(month_str))

    # 随机抽样（模拟每月库存略有不同）
    sampled = [r for r in rows_mar if rng.random() < sample_ratio]

    records = []
    batch_counter = 0
    used_batches = set()

    for row in sampled:
        batch_counter += 1

        # 生成新 batch_no（避免与3月重复）
        prefix = month_str.replace("-", "")
        new_batch = f"{prefix}{batch_counter:06d}"
        if new_batch in used_batches:
            continue
        used_batches.add(new_batch)

        # 日期偏移
        new_inbound = shift_date(row["inbound_date"], day_shift)
        new_prod = shift_date(row["production_date"], day_shift)
        new_expiry = shift_date(row["expiry_date"], day_shift)

        # 重新计算库龄
        aging_cat, aging_desc = assign_aging(new_inbound, snapshot_date)

        # 决定是否异常
        is_abn = abnormal_fn(row, rng)

        # 异常原因
        abn_reasons = None
        quality_flag = "Y"
        if is_abn:
            quality_flag = "N"
            if aging_cat in ("D", "E"):
                abn_reasons = rng.choice([
                    "不良品,超期库存(>180天),呆滞原因",
                    "不良品,超期库存(>180天),已冻结",
                    "不良品,超期库存(>180天)",
                ])
            else:
                abn_reasons = rng.choice(["不良品,已冻结", "不良品", "不良品,呆滞原因"])

        # 金额微调 ±5%
        cost = row["financial_cost"]
        if cost:
            cost = round(cost * (1 + rng.uniform(-0.05, 0.05)), 2)

        # 重量微调 ±3%
        wt = row["weight_kg"]
        if wt:
            wt = round(wt * (1 + rng.uniform(-0.03, 0.03)), 3)

        stock = row["actual_stock"]
        if stock:
            stock = round(stock * (1 + rng.uniform(-0.03, 0.03)), 3)

        records.append((
            month_str,
            new_batch,
            row["material_code"],
            row["material_name"],
            row["plant"],
            row["storage_location"],
            row["storage_loc_desc"],
            row["bin_location"],
            stock,
            wt,
            new_prod,
            new_inbound,
            new_expiry,
            quality_flag,
            row["obsolete_reason"],
            row["obsolete_reason_desc"],
            row["material_group"],
            row["material_type"],
            row["unit"],
            row["supplier_code"],
            row["supplier_batch"],
            row["supplier_name"],
            aging_cat,
            aging_desc,
            cost,
            row["production_order"],
            row["order_type"],
            row["order_type_name"],
            row["customer_code"],
            row["customer_name"],
            row["invoice_account"],
            row["invoice_account_name"],
            row["contract_code"],
            row["contract_line_item"],
            row["is_frozen"] if is_abn else 0,
            row["qc_qty"],
            row["in_transit"],
            row["currency"],
            row["rm_category"],
            row["rm_family"],
            row["category_primary"],
            1 if is_abn else 0,
            abn_reasons,
            f"{snapshot_date.isoformat()} 00:00:00",
        ))

    return records


# ── 生成 2026-01 ──────────────────────────────────────
print("生成 2026-01 ...")
jan_data = generate_month(
    "2026-01",
    snapshot_date=date(2026, 1, 31),
    day_shift=59,  # ~2个月前
    abnormal_fn=decide_abnormal_jan,
    sample_ratio=0.90,
)
print(f"  总批次: {len(jan_data)}, 异常: {sum(1 for r in jan_data if r[-2])}")

# ── 生成 2026-02 ──────────────────────────────────────
print("生成 2026-02 ...")
feb_data = generate_month(
    "2026-02",
    snapshot_date=date(2026, 2, 28),
    day_shift=28,  # ~1个月前
    abnormal_fn=decide_abnormal_feb,
    sample_ratio=0.95,
)
print(f"  总批次: {len(feb_data)}, 异常: {sum(1 for r in feb_data if r[-2])}")

# ── 插入数据库 ──────────────────────────────────────────
INSERT_SQL = """
INSERT INTO rm_inventory_snapshot (
    snapshot_month, batch_no, material_code, material_name, plant,
    storage_location, storage_loc_desc, bin_location,
    actual_stock, weight_kg, production_date, inbound_date, expiry_date,
    quality_flag, obsolete_reason, obsolete_reason_desc,
    material_group, material_type, unit, supplier_code, supplier_batch, supplier_name,
    aging_category, aging_description, financial_cost,
    production_order, order_type, order_type_name,
    customer_code, customer_name, invoice_account, invoice_account_name,
    contract_code, contract_line_item,
    is_frozen, qc_qty, in_transit, currency,
    rm_category, rm_family, category_primary,
    is_abnormal, abnormal_reasons, created_at
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

# 先清理已有的模拟数据
cur.execute("DELETE FROM rm_inventory_snapshot WHERE snapshot_month IN ('2026-01', '2026-02')")
cur.execute("DELETE FROM rm_batch_actions WHERE snapshot_month IN ('2026-01', '2026-02')")

cur.executemany(INSERT_SQL, jan_data)
cur.executemany(INSERT_SQL, feb_data)

# ── 生成 batch_actions（1月较多已完成，2月部分进行中） ──
print("生成 batch_actions ...")

# 1月：取异常批次的30%，状态为已完成/已关闭
jan_abn = [r for r in jan_data if r[-2]]  # is_abnormal=1
rng_act = random.Random(99)

jan_action_batches = rng_act.sample(jan_abn, min(int(len(jan_abn) * 0.30), len(jan_abn)))
action_records = []
depts = ["质量/研发", "PPIC&仓库", "采购", "生产", "QC"]
plans = [
    "联系供应商退货处理",
    "料废外卖",
    "1.二厂试机用；2.采购专家卖给供应商；3.料废外卖",
    "降级使用",
    "供应商换货",
    "报废处理",
]
statuses_jan = ["已完成", "已关闭"]

for r in jan_action_batches:
    batch_no = r[1]
    action_records.append((
        "2026-01", batch_no,
        rng_act.choice(["来料色差", "异味", "尺寸不良", "破损", "受潮", None]),
        rng_act.choice(depts),
        rng_act.choice(plans),
        rng_act.choice(statuses_jan),
        None,
        round(rng_act.uniform(5000, 80000), 2) if rng_act.random() < 0.3 else None,
        rng_act.choice(["CNY", "IDR"]) if rng_act.random() < 0.3 else None,
        str(date(2026, 1, 15) + timedelta(days=rng_act.randint(0, 30))),
        "2026-01-31 00:00:00",
        "2026-01-31 00:00:00",
    ))

# 2月：取异常批次的20%，状态混合
feb_abn = [r for r in feb_data if r[-2]]
feb_action_batches = rng_act.sample(feb_abn, min(int(len(feb_abn) * 0.20), len(feb_abn)))
statuses_feb = ["待处理", "讨论中", "进行中", "已完成", "已关闭"]

for r in feb_action_batches:
    batch_no = r[1]
    status = rng_act.choice(statuses_feb)
    exp_date = str(date(2026, 2, 10) + timedelta(days=rng_act.randint(0, 45)))
    action_records.append((
        "2026-02", batch_no,
        rng_act.choice(["来料色差", "异味", "尺寸不良", "破损", "受潮", "色差偏黄", None]),
        rng_act.choice(depts),
        rng_act.choice(plans),
        status,
        None,
        round(rng_act.uniform(5000, 120000), 2) if rng_act.random() < 0.4 else None,
        rng_act.choice(["CNY", "IDR"]) if rng_act.random() < 0.4 else None,
        exp_date,
        "2026-02-28 00:00:00",
        "2026-02-28 00:00:00",
    ))

ACTION_SQL = """
INSERT INTO rm_batch_actions (
    snapshot_month, batch_no, reason_note, responsible_dept,
    action_plan, action_status, remark,
    claim_amount, claim_currency, expected_completion,
    updated_at, created_at
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
"""

cur.executemany(ACTION_SQL, action_records)

conn.commit()

# ── 验证 ──────────────────────────────────────────
print("\n=== 验证 ===")
for m in ["2026-01", "2026-02", "2026-03"]:
    cur.execute(f"""
        SELECT COUNT(*), SUM(is_abnormal),
               ROUND(SUM(weight_kg)/1000,1),
               ROUND(SUM(CASE WHEN is_abnormal=1 THEN weight_kg ELSE 0 END)/1000,1)
        FROM rm_inventory_snapshot WHERE snapshot_month='{m}'
    """)
    r = cur.fetchone()
    rate = round(r[1]/r[0]*100, 1) if r[0] else 0
    wt_rate = round(r[3]/r[2]*100, 1) if r[2] else 0
    print(f"  {m}: {r[0]}批(异常{r[1]}, {rate}%), {r[2]}吨(异常{r[3]}吨, {wt_rate}%)")

cur.execute("SELECT snapshot_month, action_status, COUNT(*) FROM rm_batch_actions GROUP BY snapshot_month, action_status ORDER BY snapshot_month, action_status")
print("\n=== Action 分布 ===")
for r in cur.fetchall():
    print(f"  {r[0]} | {r[1]}: {r[2]}")

conn.close()
print("\n完成!")
