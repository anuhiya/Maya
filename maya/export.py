"""The findings and employee impact CSV exports (B7)."""
import csv
import io
from datetime import date
from decimal import Decimal
from enum import Enum

from maya import db
from maya.models import FINDINGS_EXPORT_COLUMNS, IMPACT_EXPORT_COLUMNS


def _cell(value) -> str:
    """One CSV cell: money as plain decimal text, enums as their value, empty for None."""
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _csv(columns: tuple[str, ...], rows: list[dict]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_cell(row.get(c)) for c in columns])
    return out.getvalue()


def findings_csv(findings: list, conn) -> str:
    """One row per finding with its current review status and latest decision."""
    rows = []
    for f in findings:
        decisions = db.history(conn, f.finding_id)
        last = decisions[0] if decisions else None
        row = f.model_dump()
        row.update(
            flags="; ".join(fl.name.value for fl in f.flags),
            review_status=last.status if last else "pending",
            last_comment=last.comment if last else "",
            decided_at=last.decided_at.isoformat(timespec="seconds") if last else "",
            decided_by=last.decided_by if last else "",
        )
        rows.append(row)
    return _csv(FINDINGS_EXPORT_COLUMNS, rows)


def impact_csv(impact_rows: list) -> str:
    """One row per employee and finding, every result included."""
    return _csv(IMPACT_EXPORT_COLUMNS, [r.model_dump() for r in impact_rows])


def file_name(kind: str, as_of: date) -> str:
    return f"maya_{kind}_{as_of.isoformat()}.csv"
