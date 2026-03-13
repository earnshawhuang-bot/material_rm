"""Batch action persistence service."""

from __future__ import annotations

from .. import models, schemas


def save_or_update_action(db, payload: schemas.ActionSaveRequest, updated_by: str) -> models.BatchAction:
    """Create or update one batch action record."""
    action = (
        db.query(models.BatchAction)
        .filter(
            models.BatchAction.snapshot_month == payload.snapshot_month,
            models.BatchAction.batch_no == payload.batch_no,
        )
        .first()
    )

    if action is None:
        action = models.BatchAction(
            snapshot_month=payload.snapshot_month,
            batch_no=payload.batch_no,
        )
        db.add(action)

    action.reason_note = payload.reason_note
    action.responsible_dept = payload.responsible_dept
    action.action_plan = payload.action_plan
    action.action_status = payload.action_status
    action.remark = payload.remark
    action.claim_amount = payload.claim_amount
    action.claim_currency = payload.claim_currency
    action.expected_completion = payload.expected_completion
    action.updated_by = updated_by
    db.flush()
    db.commit()
    db.refresh(action)
    return action
