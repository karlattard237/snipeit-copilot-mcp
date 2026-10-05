"""Read-only reporting and audit tracking."""

from __future__ import annotations

from typing import Any

from ..client import client_for_request
from ..errors import invalid
from ..normalizers import normalize_report
from ..schemas import REPORT_LIST_OUTPUT
from .common import action, compact, guarded, success_list

READ = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
_HISTORY_TYPES = {"hardware", "assets", "accessories", "components", "consumables", "licenses", "locations", "maintenances", "models", "suppliers", "users", "companies", "departments"}


async def reports(
    action_name: str,
    item_type: str = "hardware",
    item_id: int = 0,
    query: str = "",
    action_filter: str = "",
    user_id: int = 0,
    target_id: int = 0,
    date_from: str = "",
    date_to: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, object]:
    """Read Snipe-IT activity, one item's history, checkout/checkin history, status summaries, depreciation reports, and assets due, overdue, or due-or-overdue for audit. Results explicitly advertise both activity fields and rich asset identity fields. This tool never audits or changes records."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"activity", "item_activity", "checkout_history", "checkin_history", "status_summary", "depreciation", "audit_due", "audit_overdue", "audit_due_or_overdue"}, "reports")
        async with client_for_request() as client:
            if selected == "item_activity":
                kind = item_type.strip().lower()
                if kind not in _HISTORY_TYPES or item_id <= 0:
                    raise invalid("item_activity requires a supported item_type and positive item_id")
                endpoint = f"{kind}/{item_id}/history"
                extra = None
            elif selected == "status_summary":
                endpoint = "statuslabels/assets/name"
                extra = None
            elif selected == "depreciation":
                endpoint = "reports/depreciation"
                extra = None
            elif selected.startswith("audit_"):
                state = selected.removeprefix("audit_").replace("_", "-")
                endpoint = f"hardware/audits/{state}"
                extra = None
            else:
                endpoint = "reports/activity"
                requested_action = {"checkout_history": "checkout", "checkin_history": "checkin"}.get(selected, action_filter)
                extra = compact({"action_type": requested_action, "user_id": user_id, "target_id": target_id, "date_from": date_from, "date_to": date_to})
            rows, meta = await client.list_page(endpoint, limit=limit, offset=offset, search=query, extra=extra)
            return success_list([normalize_report(row) for row in rows], meta)

    return await guarded(run)


def register(mcp: Any) -> None:
    mcp.tool(name="reports", description=reports.__doc__, annotations=READ, output_schema=REPORT_LIST_OUTPUT)(reports)

