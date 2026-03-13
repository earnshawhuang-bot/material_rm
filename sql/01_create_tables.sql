-- ============================================================
-- rm_inventory_db 生产级建表脚本（P0）
-- 说明：
--   1) 兼容 SQL Server
--   2) 字段以 PRD 的 DDL 为主线
--   3) 保留基础索引，便于后续分页和筛选查询
-- ============================================================

IF DB_ID(N'rm_inventory_db') IS NULL
BEGIN
    PRINT N'请先在 SQL Server 上创建数据库 rm_inventory_db 并切换到该数据库';
END
GO

USE rm_inventory_db;
GO

-- ============================================================
-- 1. 库存快照表（SAP 源数据，按月上传）
-- ============================================================
IF OBJECT_ID(N'dbo.rm_inventory_snapshot', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rm_inventory_snapshot (
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
        obsolete_reason_desc NVARCHAR(100),                 -- 呆滞原因描述
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
        invoice_account_name NVARCHAR(200),                 -- 发票帐户名称
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

    CREATE INDEX idx_snapshot_month ON dbo.rm_inventory_snapshot(snapshot_month);
    CREATE INDEX idx_snapshot_plant ON dbo.rm_inventory_snapshot(plant);
    CREATE INDEX idx_snapshot_aging ON dbo.rm_inventory_snapshot(aging_category);
    CREATE INDEX idx_snapshot_abnormal ON dbo.rm_inventory_snapshot(is_abnormal);
    CREATE INDEX idx_snapshot_material ON dbo.rm_inventory_snapshot(material_code);
END
GO

-- ============================================================
-- 2. 批次处理记录表（Web 端回写）
-- ============================================================
IF OBJECT_ID(N'dbo.rm_batch_actions', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rm_batch_actions (
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
        updated_at            DATETIME DEFAULT GETDATE(),     -- 最后更新时间
        created_at            DATETIME DEFAULT GETDATE(),     -- 创建时间
        
        CONSTRAINT uq_batch_action UNIQUE (snapshot_month, batch_no)
    );

    CREATE INDEX idx_action_status ON dbo.rm_batch_actions(action_status);
    CREATE INDEX idx_action_dept ON dbo.rm_batch_actions(responsible_dept);
END
GO

-- ============================================================
-- 3. 物料主数据映射表（低频维护）
-- ============================================================
IF OBJECT_ID(N'dbo.rm_material_mapping', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.rm_material_mapping (
        id                INT IDENTITY(1,1) PRIMARY KEY,
        sku               VARCHAR(20) NOT NULL UNIQUE,    -- 物料编号
        category          VARCHAR(20),                    -- Paper/AL/PET/K-FILM 等
        family            NVARCHAR(100),                  -- 物料族
        category_primary  VARCHAR(20),                    -- 主分类
        updated_at        DATETIME DEFAULT GETDATE()
    );
END
GO

-- ============================================================
-- 4. 用户表（轻量权限管理）
-- ============================================================
IF OBJECT_ID(N'dbo.sys_users', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.sys_users (
        id              INT IDENTITY(1,1) PRIMARY KEY,
        username        VARCHAR(50) NOT NULL UNIQUE,
        password_hash   VARCHAR(255) NOT NULL,
        display_name    NVARCHAR(50),                   -- 显示名称
        department      NVARCHAR(50),                   -- 所属部门
        plant           VARCHAR(10),                    -- 所属工厂
        role            VARCHAR(10) DEFAULT 'user',     -- admin / user
        is_active       BIT DEFAULT 1,
        created_at      DATETIME DEFAULT GETDATE()
    );
END
GO

-- ============================================================
-- 5. 上传日志表（追踪数据导入历史）
-- ============================================================
IF OBJECT_ID(N'dbo.sys_upload_log', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.sys_upload_log (
        id              INT IDENTITY(1,1) PRIMARY KEY,
        snapshot_month  VARCHAR(7) NOT NULL,
        file_name       NVARCHAR(200),
        rm_type         VARCHAR(10),                       -- Paper/AL/PE
        row_count       INT,
        uploaded_by     VARCHAR(50),
        uploaded_at     DATETIME DEFAULT GETDATE(),
        status          VARCHAR(20) DEFAULT 'success'      -- success / failed
    );
    CREATE INDEX idx_upload_log_month ON dbo.sys_upload_log(snapshot_month);
END
GO

-- ============================================================
-- 6. 枚举配置表（下拉选项可维护）
-- ============================================================
IF OBJECT_ID(N'dbo.sys_enum_config', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.sys_enum_config (
        id              INT IDENTITY(1,1) PRIMARY KEY,
        enum_type       VARCHAR(50) NOT NULL,              -- dept / action_plan / action_status
        enum_value      NVARCHAR(100) NOT NULL,
        sort_order      INT DEFAULT 0,
        is_active       BIT DEFAULT 1
    );

    CREATE UNIQUE INDEX uq_enum ON dbo.sys_enum_config(enum_type, enum_value);
END
GO
