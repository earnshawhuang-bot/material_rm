# RM 系统数据库迁移一页纸（One Pager）

## 1. 目标

将当前本地 SQLite 迁移到公司服务器数据库（SQL Server），保证：

- 业务口径不变
- 历史数据可追溯
- 上传/继承/回填规则可复现
- 凭据与数据不泄露


## 2. 核心数据对象（6张表）

1. `rm_inventory_snapshot`：SAP 月快照事实表（核心库存数据）
2. `rm_batch_actions`：批次处理动作表（线上编辑 + 线下导入）
3. `rm_material_mapping`：物料映射表（分类口径来源）
4. `sys_users`：用户与权限
5. `sys_upload_log`：上传日志
6. `sys_enum_config`：枚举配置（处理状态）


## 3. 三条关键业务规则（必须一致）

1. SAP 上传规则（覆盖）
- 按 `snapshot_month + rm_type` 覆盖写入（先删后写）
- 上传后自动执行 action 继承

2. Mapping 规则（整表替换 + 历史回填）
- Mapping 上传后替换整表
- 回填历史快照中的 `rm_family/category_primary`

3. Action 规则（继承 + 补空不覆盖）
- 跨月继承按标准化 `batch_no` 匹配
- 线下导入对已有记录执行“补空不覆盖”，保护人工输入


## 4. 迁移最小步骤

1. 服务器建库并执行 SQL 基线脚本：
- `sql/01_create_tables.sql`
- `sql/02_init_enums.sql`
- `sql/03_create_views.sql`（如需 BI）

2. 后端连接切换到 SQL Server：
- `SQL_DIALECT=mssql`
- `SQL_SERVER / SQL_PORT / SQL_DATABASE / SQL_USER / SQL_PASSWORD`
- `SEED_SQLITE_DEMO=0`

3. 受控数据验证（建议用1个真实月份）：
- 上传 SAP（3类）
- 上传 Mapping
- 验证 Action 继承、导入、列表与 Dashboard 一致性


## 5. 验收清单（上线前）

1. 登录与权限正常（非 demo 账号）
2. 上传成功/失败日志可追溯
3. Dashboard 与库存明细聚合口径一致
4. Action 保存幂等（同键更新不重复）
5. 线下导入不覆盖已有非空人工字段


## 6. 风险与控制

高风险点：

- 快照月选错导致数据覆盖到错误月份
- Mapping 整表替换影响历史分类结果
- 凭据泄露到 GitHub

控制措施：

- 上传前强提醒 + 复核
- Mapping 上传后自动产出 unmatched/影响报告
- `.env` 永不入库，使用最小权限数据库账号并定期轮换密码


## 7. 当前结论

当前系统后端逻辑已具备迁移基础，重点不是“能不能迁”，而是“按统一业务宪法迁”。
建议以本页为管理层与 IT 对齐入口，以 `BACKEND_BUSINESS_CONSTITUTION.md` 作为详细实施依据。
