# PRD：原材料库存分析与处理协同平台

## 1. 项目概述

### 1.1 背景

液体包装制造企业（昆山工厂+印尼工厂），生产原材料包括纸板(Base Paper)、铝箔(Al Foil)、PE膜(PE)三大类。当前库存管理痛点：

- 计划员每月从 SAP 手动导出 3 个 Excel 文件（按原材料类型分）
- 采购/质量/研发/PPIC 等部门基于 Excel 进行异常库存分析，手工填写处理信息
- Excel 文件在多人之间传递，版本混乱、数据不一致
- 管理层通过 Power BI 查看库存报表，但缺乏处理进度的可视化

### 1.2 目标

构建一个 Web 应用，实现：

1. **数据入库**：管理员上传 SAP 导出的 Excel → 自动合并清洗 → 写入 SQL Server
2. **协同处理**：各部门人员通过 Web 端查看异常批次、填写处理信息 → 回写 SQL
3. **报表展示**：Power BI 直连 SQL Server 读取库存数据 + 处理进度

### 1.3 用户角色

| 角色 | 人数 | 核心操作 |
|------|------|----------|
| 管理员 (admin) | 1-2人 | 上传数据、管理用户、查看全局 |
| 处理人 (user) | ~8人 | 查看待处理批次、填写处理信息 |

部门包括：采购、质量、研发、PPIC（每部门约2人）

### 1.4 工厂范围

- **一期**：昆山（工厂代码 3000、3001）
- **二期**：印尼（工厂代码 3301），数据结构完全一致，货币为 IDR

---

## 2. 数据规格

### 2.1 SAP 源数据

计划员每月从 SAP 导出 3 个 Excel 文件，字段完全一致（37列），按原材料类型分：

- `Al_foil__KS_IDN__YYYYMMDD.xlsx` — 铝箔，约 1,000+ 行
- `Base_paper__KS_IDN__YYYYMMDD.xlsx` — 纸板，约 14,000+ 行
- `PE__KS_IDN__YYYYMMDD.xlsx` — PE膜，约 4,000+ 行

**37列字段定义：**

| # | 字段名 | 类型 | 说明 |
|---|--------|------|------|
| 1 | 物料编号 | VARCHAR(20) | 物料唯一编码 |
| 2 | 物料名称 | NVARCHAR(200) | 物料描述（中文） |
| 3 | 工厂 | VARCHAR(10) | 3000/3001/3301 |
| 4 | BIN位 | VARCHAR(20) | 库位，可为空 |
| 5 | 存储地点 | VARCHAR(10) | 存储地点代码 |
| 6 | 存储地点描述 | NVARCHAR(100) | 存储地点名称 |
| 7 | 批次编号 | VARCHAR(20) | **业务主键**，全局唯一 |
| 8 | 实际库存 | DECIMAL(18,3) | 当前库存数量 |
| 9 | 重量(KG) | DECIMAL(18,3) | 重量 |
| 10 | 生产日期 | DATE | |
| 11 | 入库日期 | DATE | |
| 12 | 保质期到期日期 | DATE | |
| 13 | 良品标记 | CHAR(1) | Y=良品, N=不良品 |
| 14 | 呆滞原因 | VARCHAR(10) | 呆滞原因代码，可为空 |
| 15 | 呆滞原因描述 | NVARCHAR(100) | |
| 16 | 物料组 | VARCHAR(10) | |
| 17 | 物料类型 | VARCHAR(10) | ZR01 等 |
| 18 | 单位 | VARCHAR(10) | M(米)/KG 等 |
| 19 | 供应商 | VARCHAR(20) | 供应商编码 |
| 20 | 供应商批次 | VARCHAR(50) | |
| 21 | 供应商名称 | NVARCHAR(200) | |
| 22 | 库龄分类 | CHAR(1) | A/B/C/D/E |
| 23 | 库龄分类描述 | NVARCHAR(50) | 见枚举值 |
| 24 | 财务成本额 | DECIMAL(18,2) | |
| 25 | 生产工单 | VARCHAR(20) | 可为空 |
| 26 | 订单类型 | VARCHAR(10) | 可为空 |
| 27 | 订单类型名称 | NVARCHAR(100) | 可为空 |
| 28 | 客户编码 | VARCHAR(20) | 可为空 |
| 29 | 客户名称 | NVARCHAR(200) | 可为空 |
| 30 | 发票帐户 | VARCHAR(20) | 可为空 |
| 31 | 发票帐户名称 | NVARCHAR(200) | 可为空 |
| 32 | 合同编码 | VARCHAR(20) | 可为空 |
| 33 | 合同行项目 | VARCHAR(10) | 可为空 |
| 34 | 已冻结 | INT | 0=未冻结, 非0=已冻结 |
| 35 | 质检 | DECIMAL(18,3) | 质检中数量 |
| 36 | 中转 | INT | 0=非中转 |
| 37 | 货币 | VARCHAR(5) | CNY / IDR |

### 2.2 RM Mapping 数据（物料主数据）

文件：`RM_Mapping_ks.xlsx`，约 800 条记录，低频维护。

| 字段 | 类型 | 说明 |
|------|------|------|
| Category | VARCHAR(20) | Paper/AL/PET/K-FILM/CAP-PE/LDPE/EAA/MLLDPE 等 |
| Family | VARCHAR(100) | 物料族描述 |
| SKU | VARCHAR(20) | 物料编号，与库存表的"物料编号"关联 |
| Category Primary | VARCHAR(20) | 主分类：Paper/AL/PE 等 |

### 2.3 枚举值定义

**库龄分类：**

| 代码 | 描述 | 风险等级 |
|------|------|----------|
| A | ≤30天 | 正常 |
| B | ＞30天≤90天 | 关注 |
| C | ＞90天≤180天 | 预警 |
| D | ＞180天≤360天 | 高风险 |
| E | ＞360天 | 严重 |

**责任部门（标准化下拉选项）：**

```
采购, 质量, 研发, 生产, PPIC&仓库, PPIC&质量, PPIC&生产, 采购/质量, 质量/研发, 研发/质量
```

**处理方案（标准化下拉选项）：**

```
冻结, 退货, 转内贸退货, 特采释放, 料废外卖, 按呆滞料流程处理, 绕卷, 重新绕卷, 索赔, 索赔后绕卷, 试机纸, 测试时领用, 待使用完毕一起投诉, 其他（需填备注）
```

**处理状态（标准化下拉选项）：**

```
待处理, 讨论中, 进行中, 待定, 已完成, 已关闭
```

> 注：当前 Excel 中"处理状态"字段混杂了投诉单号等备注信息，在 Web 端需要拆分为"处理状态"（下拉）+ "备注"（自由文本）两个字段。

**工厂：**

| 代码 | 名称 | 一期范围 |
|------|------|----------|
| 3000 | 昆山一厂 | ✅ |
| 3001 | 昆山二厂 | ✅ |
| 3301 | 印尼工厂 | ❌（二期） |

**原材料种类（由文件来源决定）：**

```
Paper (纸板), AL (铝箔), PE (PE膜)
```

---

## 3. 数据库设计

### 3.1 数据库信息

- **SQL Server 地址**：172.18.164.9
- **建议数据库名**：rm_inventory_db
- **字符集**：支持中文（NVARCHAR）

### 3.2 表结构 DDL

```sql
-- ============================================================
-- 1. 库存快照表（SAP 源数据，按月上传）
-- ============================================================
CREATE TABLE rm_inventory_snapshot (
    id                  INT IDENTITY(1,1) PRIMARY KEY,
    snapshot_month      VARCHAR(7) NOT NULL,          -- 期间：2026-01, 2026-02
    batch_no            VARCHAR(20) NOT NULL,          -- 批次编号（业务主键）
    material_code       VARCHAR(20),                   -- 物料编号
    material_name       NVARCHAR(200),                 -- 物料名称
    plant               VARCHAR(10),                   -- 工厂
    bin_location        VARCHAR(20),                   -- BIN位
    storage_location    VARCHAR(10),                   -- 存储地点代码
    storage_loc_desc    NVARCHAR(100),                 -- 存储地点描述
    actual_stock        DECIMAL(18,3),                 -- 实际库存
    weight_kg           DECIMAL(18,3),                 -- 重量
    production_date     DATE,                          -- 生产日期
    inbound_date        DATE,                          -- 入库日期
    expiry_date         DATE,                          -- 保质期到期日期
    quality_flag        CHAR(1),                       -- 良品标记 Y/N
    obsolete_reason     VARCHAR(10),                   -- 呆滞原因代码
    obsolete_reason_desc NVARCHAR(100),                -- 呆滞原因描述
    material_group      VARCHAR(10),                   -- 物料组
    material_type       VARCHAR(10),                   -- 物料类型
    unit                VARCHAR(10),                   -- 单位
    supplier_code       VARCHAR(20),                   -- 供应商编码
    supplier_batch      VARCHAR(50),                   -- 供应商批次
    supplier_name       NVARCHAR(200),                 -- 供应商名称
    aging_category      CHAR(1),                       -- 库龄分类 A/B/C/D/E
    aging_description   NVARCHAR(50),                  -- 库龄分类描述
    financial_cost      DECIMAL(18,2),                 -- 财务成本额
    production_order    VARCHAR(20),                   -- 生产工单
    order_type          VARCHAR(10),                   -- 订单类型
    order_type_name     NVARCHAR(100),                 -- 订单类型名称
    customer_code       VARCHAR(20),                   -- 客户编码
    customer_name       NVARCHAR(200),                 -- 客户名称
    invoice_account     VARCHAR(20),                   -- 发票帐户
    invoice_account_name NVARCHAR(200),                -- 发票帐户名称
    contract_code       VARCHAR(20),                   -- 合同编码
    contract_line_item  VARCHAR(10),                   -- 合同行项目
    is_frozen           INT DEFAULT 0,                 -- 已冻结
    qc_qty              DECIMAL(18,3) DEFAULT 0,       -- 质检中数量
    in_transit          INT DEFAULT 0,                 -- 中转
    currency            VARCHAR(5),                    -- 货币 CNY/IDR
    -- 扩展字段（来自 Mapping 和计算）
    rm_category         VARCHAR(20),                   -- 原材料种类：Paper/AL/PE
    rm_family           VARCHAR(100),                  -- 物料族（来自 Mapping）
    category_primary    VARCHAR(20),                   -- 主分类（来自 Mapping）
    -- 异常标记（上传时自动计算）
    is_abnormal         BIT DEFAULT 0,                 -- 是否异常（需要处理）
    abnormal_reasons    NVARCHAR(500),                 -- 异常原因描述（多因子）
    -- 系统字段
    created_at          DATETIME DEFAULT GETDATE(),
    
    CONSTRAINT uq_snapshot UNIQUE (snapshot_month, batch_no)
);

-- 索引
CREATE INDEX idx_snapshot_month ON rm_inventory_snapshot(snapshot_month);
CREATE INDEX idx_snapshot_plant ON rm_inventory_snapshot(plant);
CREATE INDEX idx_snapshot_aging ON rm_inventory_snapshot(aging_category);
CREATE INDEX idx_snapshot_abnormal ON rm_inventory_snapshot(is_abnormal);
CREATE INDEX idx_snapshot_material ON rm_inventory_snapshot(material_code);

-- ============================================================
-- 2. 批次处理记录表（Web 端回写）
-- ============================================================
CREATE TABLE rm_batch_actions (
    id                    INT IDENTITY(1,1) PRIMARY KEY,
    snapshot_month        VARCHAR(7) NOT NULL,          -- 关联期间
    batch_no              VARCHAR(20) NOT NULL,          -- 关联批次编号
    reason_note           NVARCHAR(500),                 -- 线下原因补充说明（自由文本）
    responsible_dept      NVARCHAR(50),                  -- 责任部门（下拉选择）
    action_plan           NVARCHAR(100),                 -- 处理方案（下拉选择）
    action_status         NVARCHAR(20) DEFAULT N'待处理', -- 处理状态（下拉选择）
    remark                NVARCHAR(500),                 -- 备注（投诉单号等补充信息）
    claim_amount          DECIMAL(18,2),                 -- 索赔金额
    claim_currency        VARCHAR(5),                    -- 币种
    expected_completion   DATE,                          -- 预计完成时间
    updated_by            VARCHAR(50),                   -- 操作人用户名
    updated_at            DATETIME DEFAULT GETDATE(),    -- 最后更新时间
    created_at            DATETIME DEFAULT GETDATE(),    -- 创建时间
    
    CONSTRAINT uq_batch_action UNIQUE (snapshot_month, batch_no)
);

CREATE INDEX idx_action_status ON rm_batch_actions(action_status);
CREATE INDEX idx_action_dept ON rm_batch_actions(responsible_dept);

-- ============================================================
-- 3. 物料主数据映射表（低频维护）
-- ============================================================
CREATE TABLE rm_material_mapping (
    id                INT IDENTITY(1,1) PRIMARY KEY,
    sku               VARCHAR(20) NOT NULL UNIQUE,     -- 物料编号
    category          VARCHAR(20),                     -- Paper/AL/PET/K-FILM 等
    family            NVARCHAR(100),                   -- 物料族
    category_primary  VARCHAR(20),                     -- 主分类
    updated_at        DATETIME DEFAULT GETDATE()
);

-- ============================================================
-- 4. 用户表（轻量权限管理）
-- ============================================================
CREATE TABLE sys_users (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    username        VARCHAR(50) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    NVARCHAR(50),                      -- 显示名称
    department      NVARCHAR(50),                      -- 所属部门
    plant           VARCHAR(10),                       -- 所属工厂
    role            VARCHAR(10) DEFAULT 'user',        -- admin / user
    is_active       BIT DEFAULT 1,
    created_at      DATETIME DEFAULT GETDATE()
);

-- ============================================================
-- 5. 上传日志表（追踪数据导入历史）
-- ============================================================
CREATE TABLE sys_upload_log (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    snapshot_month  VARCHAR(7) NOT NULL,
    file_name       NVARCHAR(200),
    rm_type         VARCHAR(10),                       -- Paper/AL/PE
    row_count       INT,
    uploaded_by     VARCHAR(50),
    uploaded_at     DATETIME DEFAULT GETDATE(),
    status          VARCHAR(20) DEFAULT 'success'      -- success / failed
);

-- ============================================================
-- 6. 枚举配置表（下拉选项可维护）
-- ============================================================
CREATE TABLE sys_enum_config (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    enum_type       VARCHAR(50) NOT NULL,              -- dept / action_plan / action_status
    enum_value      NVARCHAR(100) NOT NULL,
    sort_order      INT DEFAULT 0,
    is_active       BIT DEFAULT 1
);

-- 初始化枚举数据
INSERT INTO sys_enum_config (enum_type, enum_value, sort_order) VALUES
-- 责任部门
('dept', N'采购', 1),
('dept', N'质量', 2),
('dept', N'研发', 3),
('dept', N'生产', 4),
('dept', N'PPIC&仓库', 5),
('dept', N'PPIC&质量', 6),
('dept', N'PPIC&生产', 7),
('dept', N'采购/质量', 8),
('dept', N'质量/研发', 9),
('dept', N'研发/质量', 10),
-- 处理方案
('action_plan', N'冻结', 1),
('action_plan', N'退货', 2),
('action_plan', N'转内贸退货', 3),
('action_plan', N'特采释放', 4),
('action_plan', N'料废外卖', 5),
('action_plan', N'按呆滞料流程处理', 6),
('action_plan', N'绕卷', 7),
('action_plan', N'重新绕卷', 8),
('action_plan', N'索赔', 9),
('action_plan', N'索赔后绕卷', 10),
('action_plan', N'试机纸', 11),
('action_plan', N'测试时领用', 12),
('action_plan', N'待使用完毕一起投诉', 13),
('action_plan', N'其他', 99),
-- 处理状态
('action_status', N'待处理', 1),
('action_status', N'讨论中', 2),
('action_status', N'进行中', 3),
('action_status', N'待定', 4),
('action_status', N'已完成', 5),
('action_status', N'已关闭', 6);
```

### 3.3 关键视图（供 Power BI 使用）

```sql
-- PBI 主视图：库存 + 处理进度合并
CREATE VIEW v_inventory_with_actions AS
SELECT 
    s.*,
    a.reason_note,
    a.responsible_dept,
    a.action_plan,
    a.action_status,
    a.remark,
    a.claim_amount,
    a.claim_currency,
    a.expected_completion,
    a.updated_by AS action_updated_by,
    a.updated_at AS action_updated_at,
    CASE 
        WHEN a.action_status IS NULL THEN N'未分配'
        ELSE a.action_status 
    END AS display_status
FROM rm_inventory_snapshot s
LEFT JOIN rm_batch_actions a 
    ON s.snapshot_month = a.snapshot_month 
    AND s.batch_no = a.batch_no;
```

---

## 4. 异常判定规则

上传数据时，Python 后端自动计算 `is_abnormal` 和 `abnormal_reasons` 字段。

**一条批次记录满足以下任一条件即标记为异常：**

1. 库龄分类 ∈ {C, D, E}（即 >90天）
2. 良品标记 = 'N'
3. 已冻结 ≠ 0
4. 质检中数量 > 0
5. 呆滞原因不为空

`abnormal_reasons` 字段记录命中的规则，用逗号分隔，如：`库龄>90天,不良品,已冻结`

---

## 5. API 接口设计

### 5.1 技术栈

- **后端**：Python FastAPI
- **ORM**：SQLAlchemy（连接 SQL Server，驱动用 pymssql 或 pyodbc）
- **认证**：JWT Token（简单用户名密码登录）
- **CORS**：允许内网访问

### 5.2 接口清单

#### 认证模块

```
POST   /api/auth/login              登录，返回 JWT Token
GET    /api/auth/me                 获取当前用户信息
```

#### 数据上传模块（admin）

```
POST   /api/upload/sap-data         上传 SAP Excel 文件（支持单文件或多文件）
                                     参数：snapshot_month, rm_type(Paper/AL/PE), file
POST   /api/upload/mapping          上传/更新 RM Mapping 文件
GET    /api/upload/history          查看上传历史日志
DELETE /api/upload/{snapshot_month}  删除某月快照（重新上传用）
```

#### 库存查询模块

```
GET    /api/inventory/list          分页查询库存列表
                                     查询参数：snapshot_month, plant, rm_category, 
                                     aging_category, is_abnormal, quality_flag,
                                     material_code, supplier_name, keyword,
                                     page, page_size, sort_by, sort_order
GET    /api/inventory/summary       库存汇总统计（按库龄/类别/工厂）
GET    /api/inventory/{batch_no}    单个批次详情（含处理记录）
GET    /api/inventory/months        获取已有快照月份列表
```

#### 处理记录模块

```
GET    /api/actions/pending         获取待处理批次列表（按部门筛选）
POST   /api/actions/save            保存/更新处理记录
                                     body: { snapshot_month, batch_no, responsible_dept,
                                             action_plan, action_status, reason_note,
                                             remark, claim_amount, claim_currency,
                                             expected_completion }
GET    /api/actions/export          导出处理记录为 Excel
```

#### 枚举配置模块

```
GET    /api/enums/{enum_type}       获取枚举选项列表（dept/action_plan/action_status）
POST   /api/enums                   新增枚举值（admin）
```

#### 用户管理模块（admin）

```
GET    /api/users                   用户列表
POST   /api/users                   创建用户
PUT    /api/users/{id}              更新用户
```

---

## 6. 前端页面设计

### 6.1 技术栈

- **框架**：HTML + Tailwind CSS + Alpine.js（轻量级，无需构建工具）
- **或**：Vue 3 + Vite（如需更好的组件化）
- **设计风格**：简洁清爽，专业感，中文界面
- **响应式**：主要适配桌面端（1280px+），兼顾平板

### 6.2 页面结构

```
/login                     登录页
/dashboard                 仪表盘首页（管理员和用户共用，内容按角色不同）
/inventory                 库存明细列表（可筛选、排序、搜索）
/inventory/:batch_no       批次详情 + 处理表单
/pending                   待处理任务列表（按当前用户部门预筛选）
/admin/upload              数据上传页面（仅 admin）
/admin/users               用户管理（仅 admin）
/admin/enums               枚举配置（仅 admin）
```

### 6.3 核心页面详细设计

#### 页面1：仪表盘 `/dashboard`

**顶部统计卡片（4个）：**
- 当月库存总批次数
- 异常批次数（及占比）
- 待处理数（未分配 + 待处理状态）
- 已完成处理数

**中部图表（2个）：**
- 左：库龄分布柱状图（按 A/B/C/D/E，分颜色）
- 右：按原材料类别的异常占比饼图

**底部快速入口：**
- "查看待处理批次" → 跳转 /pending
- "上传本月数据" → 跳转 /admin/upload（仅 admin 可见）

#### 页面2：库存明细 `/inventory`

**顶部筛选栏（一行展示）：**
- 快照月份（下拉，默认最新月）
- 工厂（下拉，多选）
- 原材料类别（Paper/AL/PE，多选）
- 库龄分类（A-E，多选）
- 是否异常（全部/仅异常/仅正常）
- 关键词搜索（物料编号/名称/供应商模糊搜索）

**数据表格：**
- 列：物料编号、物料名称、批次编号、工厂、库龄分类（带颜色标签）、实际库存、重量KG、财务成本额、良品标记、处理状态（带颜色标签）、操作
- 库龄颜色：A=绿, B=蓝, C=黄, D=橙, E=红
- 处理状态颜色：待处理=灰, 讨论中=蓝, 进行中=黄, 已完成=绿, 已关闭=灰
- "操作"列：点击"处理"按钮 → 进入批次详情页
- 支持分页（每页 50 条）、列排序
- 支持导出当前筛选结果为 Excel

#### 页面3：批次详情 + 处理表单 `/inventory/:batch_no`

**上半部分：批次基本信息（只读展示）**

分两列卡片布局：
- 左卡片：物料编号、物料名称、原材料类别、物料族
- 右卡片：工厂、存储地点、BIN位、供应商名称
- 下方行：批次编号、实际库存、重量、财务成本额、库龄分类（大号彩色标签）、良品标记、入库日期、保质期到期日期

**下半部分：处理信息表单（可编辑）**

| 字段 | 控件类型 | 必填 |
|------|----------|------|
| 责任部门 | 下拉选择 | ✅ |
| 处理方案 | 下拉选择 | ✅ |
| 处理状态 | 下拉选择 | ✅ |
| 线下原因补充说明 | 多行文本框 | ❌ |
| 备注 | 多行文本框（投诉单号等） | ❌ |
| 索赔金额 | 数字输入 | ❌ |
| 币种 | 下拉选择（CNY/IDR） | 索赔金额有值时必填 |
| 预计完成时间 | 日期选择器 | ❌ |

按钮：保存（提交到 API） / 返回列表

**处理历史：** 表单下方显示该批次的修改历史记录（谁在什么时间改了什么）

#### 页面4：待处理任务 `/pending`

- 与库存明细类似的表格，但默认预筛选：
  - 仅显示 is_abnormal = 1 的批次
  - 如果是 user 角色，进一步筛选 responsible_dept = 当前用户部门 OR action_status IS NULL（未分配的也展示）
- 支持快速批量操作：勾选多个批次 → 批量设置责任部门

#### 页面5：数据上传 `/admin/upload`

**上传区域：**
- 选择快照月份（YYYY-MM 格式）
- 三个上传区域分别对应：纸板 / 铝箔 / PE
- 支持拖拽上传
- 上传前校验：文件格式、列名是否匹配
- 上传后显示：导入行数、异常批次数、处理耗时

**可选：** 同一个上传入口，上传 RM_Mapping 文件更新物料主数据

**上传历史列表：** 显示历史上传记录（月份、文件名、行数、上传人、时间）

**重要逻辑：** 如果该月份已有数据，提示"将覆盖已有快照数据，但不会影响已填写的处理记录"。

---

## 7. 数据处理逻辑

### 7.1 上传流程（Python 后端）

```python
# 伪代码：SAP Excel 上传处理流程
def process_upload(file, snapshot_month, rm_type):
    # 1. 读取 Excel
    df = pd.read_excel(file)
    
    # 2. 校验列名（必须与 SAP 37列一致）
    validate_columns(df)
    
    # 3. 添加原材料类别
    df['rm_category'] = rm_type  # Paper / AL / PE
    
    # 4. 关联 Mapping 表，补充 category/family/category_primary
    mapping = load_mapping_from_db()
    df = df.merge(mapping, left_on='物料编号', right_on='sku', how='left')
    
    # 5. 计算异常标记
    df['is_abnormal'] = (
        (df['库龄分类'].isin(['C', 'D', 'E'])) |
        (df['良品标记'] == 'N') |
        (df['已冻结'] != 0) |
        (df['质检'] > 0) |
        (df['呆滞原因'].notna())
    ).astype(int)
    
    # 6. 生成异常原因描述
    df['abnormal_reasons'] = generate_reasons(df)
    
    # 7. 删除该月份+该类别的旧数据
    delete_snapshot(snapshot_month, rm_type)
    
    # 8. 写入 SQL Server
    write_to_sql(df, 'rm_inventory_snapshot')
    
    # 9. 记录上传日志
    log_upload(snapshot_month, rm_type, file.filename, len(df))
```

### 7.2 字段名映射（中文 → 英文）

```python
COLUMN_MAPPING = {
    '物料编号': 'material_code',
    '物料名称': 'material_name',
    '工厂': 'plant',
    'BIN位': 'bin_location',
    '存储地点': 'storage_location',
    '存储地点描述': 'storage_loc_desc',
    '批次编号': 'batch_no',
    '实际库存': 'actual_stock',
    '重量(KG)': 'weight_kg',
    '生产日期': 'production_date',
    '入库日期': 'inbound_date',
    '保质期到期日期': 'expiry_date',
    '良品标记': 'quality_flag',
    '呆滞原因': 'obsolete_reason',
    '呆滞原因描述': 'obsolete_reason_desc',
    '物料组': 'material_group',
    '物料类型': 'material_type',
    '单位': 'unit',
    '供应商': 'supplier_code',
    '供应商批次': 'supplier_batch',
    '供应商名称': 'supplier_name',
    '库龄分类': 'aging_category',
    '库龄分类描述': 'aging_description',
    '财务成本额': 'financial_cost',
    '生产工单': 'production_order',
    '订单类型': 'order_type',
    '订单类型名称': 'order_type_name',
    '客户编码': 'customer_code',
    '客户名称': 'customer_name',
    '发票帐户': 'invoice_account',
    '发票帐户名称': 'invoice_account_name',
    '合同编码': 'contract_code',
    '合同行项目': 'contract_line_item',
    '已冻结': 'is_frozen',
    '质检': 'qc_qty',
    '中转': 'in_transit',
    '货币': 'currency',
}
```

---

## 8. 非功能需求

### 8.1 性能

- 数据量：单月约 20,000 行，12个月快照约 240,000 行，SQL Server 轻松应对
- 并发：最多 8-10 个同时在线用户
- 页面加载：< 2秒

### 8.2 安全

- 内网部署（172.18.164.9），无公网暴露
- JWT Token 过期时间：8小时（一个工作日）
- 密码存储：bcrypt 哈希

### 8.3 部署

- 服务器：172.18.164.9（已有 SQL Server）
- Python 环境：建议 Python 3.10+
- Web 服务：Uvicorn + FastAPI
- 前端：直接由 FastAPI 的 static files 功能提供，或 Nginx 反向代理
- 端口建议：8080（Web 应用）

### 8.4 后续扩展（二期）

- 印尼工厂（3301）数据接入
- 邮件通知：批次被分配时自动通知责任人
- 处理超期提醒
- 月度处理报告自动生成
- SAP 数据自动抽取（如果 IT 能提供接口）

---

## 9. 项目结构（建议）

```
rm-inventory-platform/
├── backend/
│   ├── main.py                  # FastAPI 入口
│   ├── config.py                # 配置（数据库连接、JWT 密钥等）
│   ├── database.py              # SQLAlchemy 引擎和会话管理
│   ├── models.py                # ORM 模型定义
│   ├── schemas.py               # Pydantic 请求/响应模型
│   ├── auth.py                  # 认证逻辑（JWT）
│   ├── routers/
│   │   ├── auth.py              # /api/auth/*
│   │   ├── upload.py            # /api/upload/*
│   │   ├── inventory.py         # /api/inventory/*
│   │   ├── actions.py           # /api/actions/*
│   │   ├── enums.py             # /api/enums/*
│   │   └── users.py             # /api/users/*
│   ├── services/
│   │   ├── upload_service.py    # Excel 解析、清洗、入库逻辑
│   │   ├── inventory_service.py # 库存查询逻辑
│   │   └── action_service.py    # 处理记录逻辑
│   └── requirements.txt
├── frontend/
│   ├── index.html               # 入口（SPA 或多页面）
│   ├── css/
│   ├── js/
│   └── pages/
│       ├── login.html
│       ├── dashboard.html
│       ├── inventory.html
│       ├── batch-detail.html
│       ├── pending.html
│       └── admin/
│           ├── upload.html
│           ├── users.html
│           └── enums.html
├── sql/
│   ├── 01_create_tables.sql     # 建表脚本
│   ├── 02_init_enums.sql        # 枚举初始化
│   └── 03_create_views.sql      # PBI 视图
├── .cursorrules                  # Cursor 项目规则
├── .env                          # 环境变量（数据库密码等，不提交 git）
├── README.md
└── PRD.md                        # 本文档
```

---

## 10. 开发优先级

### P0 - MVP（第1-2周）

1. 数据库建表 + 初始化枚举
2. 后端：Excel 上传解析 + 写入 SQL
3. 后端：库存列表查询 API + 处理记录保存 API
4. 前端：登录页 + 库存列表页 + 批次处理表单页
5. 前端：管理员上传页面

### P1 - 完善（第3周）

6. 仪表盘页面（统计卡片 + 图表）
7. 待处理任务页面（预筛选逻辑）
8. 用户管理页面
9. PBI 视图创建 + 连接验证

### P2 - 优化（第4周）

10. 导出 Excel 功能
11. 批量操作（批量分配责任部门）
12. 处理历史记录
13. 枚举配置管理页面
