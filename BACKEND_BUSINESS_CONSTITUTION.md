# RM Inventory Backend Business Constitution

## 1. Purpose

This document is the single source of truth for backend data behavior before database migration.
It defines:

- Which tables exist and what each table is responsible for
- How CRUD is performed (API -> service -> table)
- What the real business rules are (overwrite, carry-forward, matching, filtering)
- What must be protected during migration

Scope: `backend/` + `sql/` only.


## 2. Data Model (6 Core Tables)

### 2.1 `rm_inventory_snapshot`

Purpose:

- Monthly SAP snapshot fact table (inventory batch-level facts)

Key constraints:

- Unique: `(snapshot_month, batch_no)`

Important fields:

- Snapshot identity: `snapshot_month`, `batch_no`
- Inventory facts: `weight_kg`, `financial_cost`, `currency`, `aging_category`, `quality_flag`, `plant`
- Enrichment: `plant_group`, `rm_category`, `rm_family`, `category_primary`
- Flags: `is_abnormal`, `abnormal_reasons`


### 2.2 `rm_batch_actions`

Purpose:

- Manual/offline action tracking for each batch in each month

Key constraints:

- Unique: `(snapshot_month, batch_no)`

Important fields:

- Action body: `reason_note`, `responsible_dept`, `action_plan`, `action_status`, `remark`
- Financial follow-up: `claim_amount`, `claim_currency`
- Timeline: `expected_completion`
- Audit: `updated_by`, `updated_at`, `created_at`


### 2.3 `rm_material_mapping`

Purpose:

- Material master mapping used for category/family enrichment

Key constraints:

- Unique: `sku`

Important fields:

- `sku`, `category`, `family`, `category_primary`


### 2.4 `sys_users`

Purpose:

- User authentication/authorization

Important fields:

- `username`, `password_hash`, `role`, `is_active`


### 2.5 `sys_upload_log`

Purpose:

- Upload operation history (success/failure trace)

Important fields:

- `snapshot_month`, `file_name`, `rm_type`, `row_count`, `uploaded_by`, `status`, `uploaded_at`


### 2.6 `sys_enum_config`

Purpose:

- Enum source (currently mainly action status)

Business rule:

- Canonical action statuses are restricted to 3 states:
  - `待定`
  - `进行中`
  - `已完成`


## 3. CRUD Matrix (What Writes/Reads Which Table)

| Domain | API | Table(s) | Operation Type | Core Rule |
|---|---|---|---|---|
| SAP upload (single) | `POST /api/upload/sap-data` | `rm_inventory_snapshot`, `sys_upload_log`, `rm_batch_actions` | Delete + Insert + Log + Carry-forward | Overwrite current `snapshot_month + rm_type`; then carry-forward actions |
| SAP upload (batch) | `POST /api/upload/sap-data/batch` | same as above | Same as above for 3 files | Must include Paper/AL/PE each once |
| Mapping upload | `POST /api/mapping/upload` | `rm_material_mapping`, `rm_inventory_snapshot` | Replace all + Backfill | Mapping table full replace, then backfill historical snapshots |
| Offline action import | `POST /api/upload/action-import` | `rm_batch_actions` | Upsert-like (fill-empty) | Match by normalized batch no; do not overwrite non-empty user values |
| Action save (UI row) | `POST /api/actions/save` | `rm_batch_actions` | Upsert | Key = `snapshot_month + normalized_batch_no` |
| Inventory list/stats | `GET /api/inventory/*` | `rm_inventory_snapshot` + `rm_batch_actions` + `rm_material_mapping` | Read | Filters and metrics rely on mapping + normalized status |
| Dashboard | `GET /api/dashboard/overview` | `rm_inventory_snapshot` + `rm_batch_actions` | Read | GM metrics, risk composition, top suppliers |
| Auth/User | `POST /api/auth/login`, `GET/POST/PUT /api/users` | `sys_users` | Read/Insert/Update | Password hash + role-based admin control |
| Upload history | `GET /api/upload/history` | `sys_upload_log` | Read | Admin traceability |
| Enum read | `GET /api/enums/{enum_type}` | `sys_enum_config` | Read | Action status normalized to 3-state canonical order |


## 4. 核心业务规则 / Canonical Business Rules

### 4.1 SAP 上传规则（快照覆盖） / SAP Upload Rule (Snapshot Overwrite)

中文说明：

1. 解析 Excel，并标准化关键字段（批次号、物料号、工厂）。
2. 文件内按 `batch_no` 去重，保留最后一条。
3. 计算异常标记（`quality_flag == "N"` 视为异常）。
4. 用 Mapping 表补充分类信息（`material_code` -> `rm_family/category_primary`）。
5. 覆盖写入目标分片：
   - 先删除 `snapshot_month == 输入月份` 且 `rm_category == 输入类型` 的历史数据
   - 再批量写入新数据
6. 写入上传日志 `sys_upload_log`。
7. 执行 action 历史继承（carry-forward）。

English:

1. Parse Excel and normalize key fields (batch/material/plant).
2. Deduplicate by `batch_no` within file and keep the last row.
3. Derive abnormal flags (`quality_flag == "N"` => abnormal).
4. Enrich using mapping (`material_code` -> `rm_family/category_primary`).
5. Overwrite target slice by delete-then-insert.
6. Write upload log.
7. Run action carry-forward.

业务结果 / Practical consequence:

- SAP 数据以“月快照”管理，不是追加流水。
- 同月同类型重复上传会覆盖该分片数据。


### 4.2 Mapping 规则（整表替换 + 历史回填） / Mapping Rule (Full Replace + Historical Backfill)

中文说明：

1. 上传 Mapping 时，`rm_material_mapping` 采用整表替换。
2. 替换后立即对历史快照执行回填：
   - 按标准化后的物料号匹配
   - 更新 `rm_family` 和 `category_primary`

English:

1. Mapping upload fully replaces `rm_material_mapping`.
2. Then historical snapshots are backfilled by normalized material code.

业务结果 / Practical consequence:

- Mapping 不只在 SAP 上传瞬间生效。
- Mapping 更新可追溯修正历史月份的分类口径。


### 4.3 Action 继承规则（跨月继承） / Action Carry-forward Rule (Historical Inheritance)

中文说明：

- 触发时机：每次 SAP 上传完成后自动执行。
- 匹配键：标准化后的 `batch_no`。
- 来源：历史月份最新 action（`snapshot_month < 新月份`）。
- 目标：新月份快照中存在的批次。
- 保护策略：若新月份该批次已有 action，则跳过，不覆盖人工记录。

English:

- Triggered automatically after SAP upload.
- Matched by normalized `batch_no`.
- Source is latest historical action (`snapshot_month < new_month`).
- Existing action in target month is protected and not overwritten.


### 4.4 线下 Action 导入规则（批量补录） / Offline Action Import Rule (Bulk Assistance)

中文说明：

1. 读取线下 Excel。
2. 必须包含批次号列。
3. 仅处理“目标月份 + 异常批次”。
4. 处理状态统一标准化为三态：`待定 / 进行中 / 已完成`。
5. 若目标月已存在 action，采用“补空不覆盖”（fill-empty-only）。
6. 若目标月不存在 action，则新增。

English:

1. Read offline Excel rows.
2. Require batch number column.
3. Process only abnormal batches of target month.
4. Normalize status to canonical 3 states.
5. Existing row uses fill-empty-only merge.
6. Missing row is inserted.

业务结果 / Practical consequence:

- 兼容一次性线下数据补录场景。
- 保护线上已录入人工信息，避免被导入覆盖。


### 4.5 匹配与标准化规则 / Matching and Normalization Rules

批次号与物料号 / Batch & material key normalization:

- 批次号、物料号都按“文本键”处理。
- 自动修正 Excel 常见数值化问题（如 `.0`、科学计数法）。
- 对真实文本编号保留前导 0。

工厂逻辑 / Plant logic:

- 工厂分组映射：
  - `3000`, `3001` -> `KS`
  - `3301` -> `IDN`

状态逻辑 / Status logic:

- 所有状态输入最终归一到三态：
  - `待定`
  - `进行中`
  - `已完成`


### 4.6 Dashboard 与库存明细口径 / Dashboard and Inventory Semantics

中文说明：

- 主单位为吨：`weight_kg / 1000`，展示优先整数化。
- 不良原因熵减规则：
  - 呆滞原因描述含 `原材料过期` 或 `库存逾期` -> `超期`
  - 其余不良 -> `质量不良`
- 供应商风险图当前为异常品 Top 8（按吨数）。
- 类别筛选来源于 Mapping 匹配结果（`material_code <-> sku`），不是直接取 SAP 原始分类文本。

English:

- Weight is represented in tons (`weight_kg / 1000`) with integer-oriented display.
- Reason entropy reduction maps to two buckets: `超期` and `质量不良`.
- Supplier panel is Top 8 by abnormal tons.
- Category filter is mapping-driven (`material_code <-> sku`), not raw SAP text.


## 5. 数据一致性与风险边界 / Data Consistency and Risk Boundaries

### 5.1 明确假设 / Explicit assumptions

- `batch_no` 在跨月场景中可作为 action 继承的稳定业务标识。
- 同一个月内，同一 `batch_no` 不应跨 RM 类型冲突（受唯一约束 `(snapshot_month, batch_no)` 保护）。

### 5.2 重点风险点 / Risk points to monitor

- 上传时误选快照月（人为操作风险）。
- Mapping 整表替换会影响所有历史月份的分类结果。
- 低质量线下导入文件可能注入噪声文本，影响可读性与统计一致性。


## 6. 迁移宪法（必须控制项） / Migration Constitution (Must-Have Controls)

### 6.1 迁移前 / Before migration

1. 在服务器数据库执行：
   - `sql/01_create_tables.sql`
   - `sql/02_init_enums.sql`
   - `sql/03_create_views.sql`（若需要 BI 视图）
2. 确认 SQL Server 权限完整：
   - DDL：create/alter/index/view
   - DML：insert/update/delete/select
3. 本文档规则与 PRD 完成业务签字（sign-off）。

### 6.2 切换检查 / Migration cutover checks

1. 环境变量切到 `mssql` 连接。
2. 生产/准生产关闭本地种子：`SEED_SQLITE_DEMO=0`。
3. 选一个受控月份做端到端验证：
   - 快照覆盖是否正确
   - Action 继承是否正确
   - Mapping 历史回填是否正确
   - 状态归一化是否正确

### 6.3 迁移后冒烟测试 / Post-migration smoke tests

1. 非 demo 账号登录正常。
2. 上传日志能记录成功与失败。
3. Dashboard 与库存明细在同筛选条件下聚合口径一致。
4. 库存明细 action 保存满足幂等（同键更新，不重复新增）。
5. 线下导入不会覆盖已有非空人工字段。

## 7. Source of Truth (Code Locations)

- Models: `backend/models.py`
- DB bootstrap: `backend/main.py`, `backend/database.py`, `backend/services/bootstrap.py`
- Upload pipeline: `backend/routers/upload.py`, `backend/services/upload_service.py`
- Mapping pipeline: `backend/routers/mapping.py`, `backend/services/mapping_service.py`
- Action pipeline: `backend/routers/actions.py`, `backend/services/action_service.py`
- Inventory query: `backend/routers/inventory.py`, `backend/services/inventory_service.py`
- Dashboard query: `backend/routers/dashboard.py`
- SQL baseline: `sql/01_create_tables.sql`, `sql/02_init_enums.sql`, `sql/03_create_views.sql`


## 8. Change Management Rule

Any future backend logic change touching upload, mapping, action inheritance, or status semantics must update this document in the same PR.

