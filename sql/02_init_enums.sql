-- ============================================================
-- PRD 枚举表初始化（幂等写法）
-- 说明：
--   责任部门 (dept) 和 处理方案 (action_plan) 已改为自由文本输入，
--   不再需要枚举数据。仅保留 action_status 的枚举项。
-- ============================================================

USE rm_inventory_db;
GO

SET NOCOUNT ON;
GO

-- 处理状态（唯一保留的枚举）
IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'action_status' AND enum_value = N'待处理'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'action_status', N'待处理', 1);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'action_status' AND enum_value = N'讨论中'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'action_status', N'讨论中', 2);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'action_status' AND enum_value = N'进行中'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'action_status', N'进行中', 3);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'action_status' AND enum_value = N'待定'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'action_status', N'待定', 4);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'action_status' AND enum_value = N'已完成'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'action_status', N'已完成', 5);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'action_status' AND enum_value = N'已关闭'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'action_status', N'已关闭', 6);
