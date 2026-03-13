-- ============================================================
-- PBI 视图：库存 + 处理信息
-- ============================================================

USE rm_inventory_db;
GO

IF OBJECT_ID(N'dbo.v_inventory_with_actions', N'V') IS NOT NULL
    DROP VIEW dbo.v_inventory_with_actions;
GO

CREATE VIEW dbo.v_inventory_with_actions
AS
SELECT 
    s.id,
    s.snapshot_month,
    s.batch_no,
    s.material_code,
    s.material_name,
    s.plant,
    s.storage_location,
    s.storage_loc_desc,
    s.bin_location,
    s.actual_stock,
    s.weight_kg,
    s.financial_cost,
    s.production_date,
    s.inbound_date,
    s.expiry_date,
    s.currency,
    s.aging_category,
    s.aging_description,
    s.quality_flag,
    s.rm_category,
    s.rm_family,
    s.category_primary,
    s.is_abnormal,
    s.abnormal_reasons,
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
FROM dbo.rm_inventory_snapshot s
LEFT JOIN dbo.rm_batch_actions a
    ON s.snapshot_month = a.snapshot_month
    AND s.batch_no = a.batch_no;
GO
