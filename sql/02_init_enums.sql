-- ============================================================
-- PRD 枚举表初始化（幂等写法）
-- 说明：
--   同一个 (enum_type, enum_value) 可能多次执行，使用 NOT EXISTS 防重复
-- ============================================================

USE rm_inventory_db;
GO

SET NOCOUNT ON;
GO

-- 责任部门
IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'dept' AND enum_value = N'采购'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'dept', N'采购', 1);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'dept' AND enum_value = N'质量'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'dept', N'质量', 2);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'dept' AND enum_value = N'研发'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'dept', N'研发', 3);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'dept' AND enum_value = N'生产'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'dept', N'生产', 4);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'dept' AND enum_value = N'PPIC&仓库'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'dept', N'PPIC&仓库', 5);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'dept' AND enum_value = N'PPIC&质量'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'dept', N'PPIC&质量', 6);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'dept' AND enum_value = N'PPIC&生产'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'dept', N'PPIC&生产', 7);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'dept' AND enum_value = N'采购/质量'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'dept', N'采购/质量', 8);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'dept' AND enum_value = N'质量/研发'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'dept', N'质量/研发', 9);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'dept' AND enum_value = N'研发/质量'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'dept', N'研发/质量', 10);

-- 处理方案
IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'action_plan' AND enum_value = N'冻结'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'action_plan', N'冻结', 1);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'action_plan' AND enum_value = N'退货'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'action_plan', N'退货', 2);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'action_plan' AND enum_value = N'转内贸退货'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'action_plan', N'转内贸退货', 3);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'action_plan' AND enum_value = N'特采释放'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'action_plan', N'特采释放', 4);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'action_plan' AND enum_value = N'料废外卖'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'action_plan', N'料废外卖', 5);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'action_plan' AND enum_value = N'按呆滞料流程处理'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'action_plan', N'按呆滞料流程处理', 6);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'action_plan' AND enum_value = N'绕卷'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'action_plan', N'绕卷', 7);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'action_plan' AND enum_value = N'重新绕卷'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'action_plan', N'重新绕卷', 8);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'action_plan' AND enum_value = N'索赔'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'action_plan', N'索赔', 9);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'action_plan' AND enum_value = N'索赔后绕卷'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'action_plan', N'索赔后绕卷', 10);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'action_plan' AND enum_value = N'试机纸'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'action_plan', N'试机纸', 11);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'action_plan' AND enum_value = N'测试时领用'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'action_plan', N'测试时领用', 12);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'action_plan' AND enum_value = N'待使用完毕一起投诉'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'action_plan', N'待使用完毕一起投诉', 13);

IF NOT EXISTS (
    SELECT 1
    FROM dbo.sys_enum_config
    WHERE enum_type = 'action_plan' AND enum_value = N'其他'
)
    INSERT INTO dbo.sys_enum_config (enum_type, enum_value, sort_order) VALUES (N'action_plan', N'其他', 99);

-- 处理状态
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
