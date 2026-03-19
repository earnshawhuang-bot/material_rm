# RM 库存异常处理协同平台（开发中）

## 目前完成内容（P0 起步）

- SQL Server 建表脚本：`sql/01_create_tables.sql`
- 枚举初始化脚本：`sql/02_init_enums.sql`
- PBI 视图脚本：`sql/03_create_views.sql`
- FastAPI 后端骨架：`backend/`
  - 入口：`backend/main.py`
  - 数据库配置：`backend/config.py`
  - ORM：`backend/models.py`
  - Schema：`backend/schemas.py`
  - 认证：`backend/auth.py`
  - 路由：
    - `backend/routers/auth.py`
    - `backend/routers/upload.py`
    - `backend/routers/inventory.py`
    - `backend/routers/actions.py`（`/api/actions/save` 已可用）
    - `backend/routers/enums.py`
- `backend/routers/mapping.py`
    - `backend/routers/users.py`
  - 服务层：
    - `backend/services/upload_service.py`
    - `backend/services/inventory_service.py`
    - `backend/services/action_service.py`
    - `backend/services/auth_service.py`
- `backend/services/mapping_service.py`

## 下一步

1. `sql` 目录脚本先在 SQL Server 执行，创建基础数据结构与枚举。
2. 在 `backend` 下配置 `.env`（可先复制 `.env.example`）并安装依赖。
3. 运行 `uvicorn backend.main:app --reload` 启动后端，先验证登录、上传、库存列表和处理保存 API。
4. 与您确认后继续补齐前端页（P0 的登录、库存列表、批次处理页、上传页）。

## SQLite 本地 Demo（你现在可直接预览）

### 1. 设置环境变量
- 复制 `backend/.env.example` 为 `backend/.env`
- 确保以下项（本地默认）：
  - `SQL_DIALECT=sqlite`
  - `SQLITE_PATH=backend/rm_inventory_demo.db`
  - `SEED_SQLITE_DEMO=1`
  - `DEFAULT_ADMIN_USERNAME=admin`
  - `DEFAULT_ADMIN_PASSWORD=123456`

### 2. 安装依赖并启动

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8080
```

### 3. 打开浏览器
- 地址：`http://127.0.0.1:8080/`
- 默认账户：`admin / 123456`
- 首次启动会自动创建本地 SQLite 库并写入：
  - admin 用户
  - 枚举配置
  - 两条示例库存与一条处理记录（用于可视化验证）

### 4. 迁移到正式 SQL Server
- 不改代码，修改 `.env`：
  - `SQL_DIALECT=mssql`
  - `SQL_SERVER=172.18.164.9`（按你的正式库）
  - `SQL_DATABASE=rm_inventory_db`
  - `SQL_USER / SQL_PASSWORD`
  - `SEED_SQLITE_DEMO=0`
- 重启服务后，系统将改走 SQL Server。
- SQL Server 仍建议先执行你那套 `sql/*.sql` 建表脚本和枚举初始化脚本。

### 5. 一步三文件上传（一个上传口）
- 管理界面“管理员快速上传”现提供一个上传口，可直接从文件夹一次选 1~3 个文件（Paper/AL/PE）一次提交。
- 前端新增“严格模式”开关：
  - 关闭：支持 1~3 个文件用于单类修订，不影响现场修复。
  - 开启：必须 Paper/AL/PE 三类齐全且各一份，否则阻断提交。
- 上传接口自动按文件名推断类型：
  - `Base_paper` / `Paper` 关键字 → `Paper`
  - `Al_foil` / `AL` 关键字 → `AL`
  - `PE` 关键字 → `PE`
- 文件名中至少要包含上述关键字之一（如 `2026-03_Paper.xlsx`），否则会被拒绝。
- 你仍可以继续走单文件旧接口：
  - `POST /api/upload/sap-data`
- 推荐在页面统一使用新接口：
  - `POST /api/upload/sap-data/batch`
- 上传接口会校验 `snapshot_month` 必须是 `YYYY-MM`。

### 6. Mapping 表维护（业务侧覆盖上传）
- 新增映射接口：
  - `GET /api/mapping`：查看当前映射
  - `POST /api/mapping/upload`：覆盖式上传 `rm_material_mapping`
- 上传文件要求包含字段（可用中文或英文）：
  - `sku` / `物料编码`（必填）
  - `category` / `类别`（可选）
  - `family` / `家族`（可选）
  - `category_primary` / `一级分类`（可选）
- 上传成功会先清空历史映射，再按文件内容重建映射表。

## 编码与乱码防护（必读）

- 规范文档：`ENCODING_RULES.md`
- 修改前后都执行编码检查：
  - `python scripts/check_encoding.py`
  - 或（Windows）`powershell -ExecutionPolicy Bypass -File scripts/check_encoding.ps1`
- PowerShell 读取/写入文件时必须显式 UTF-8 编码，禁止默认编码读写。
