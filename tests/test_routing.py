"""Auto-approval rule, review reasons, Pre-approve and sign-off (A3, V6)."""
from decimal import Decimal as D

import pytest

from maya import db, routing
from maya.flags import date_flag
from maya.models import (Category as C, ChangeType as CT, CheckResult, Finding, Flag, FlagName,
                         Status, Timing)
from maya.site import load_config

JURISDICTIONS = ["Avalon", "Calder", "Meridian"]
PASSED = [CheckResult(check=c, passed=True) for c in ("V1", "V2", "V3")]


def finding(section, jur, cat, change, old, new, date, *, flags=(), checks=PASSED):
    flags = list(flags)
    if (flag := date_flag(date)):
        flags.append(flag)
    return Finding(finding_id=f"f{section}", section=section, jurisdiction=jur, category=cat, change_type=change,
                   old_value=D(old) if old else None, new_value=D(new) if new else None,
                   effective_date=date, timing=Timing.FUTURE, source_file="gov_rules_v2.txt",
                   flags=flags, check_results=list(checks))


WORDING = Flag(name=FlagName.NEW_WORDING, reason="Reworded.")

# The nine findings of docs/expected.md and the route written there.
EXPECTED = {
    "1.1": (finding("1.1", "Avalon", C.WAGES, CT.SUBSTANTIVE, "16.00", "17.25", "November 1, 2026"), []),
    "1.2": (finding("1.2", "Avalon", C.TAX_RATE, CT.SUBSTANTIVE, "2.7", "3.1", "January 1, 2027"), []),
    "1.3": (finding("1.3", "Avalon", C.REPORTING, CT.SUBSTANTIVE, None, None, "January 1, 2027",
                    flags=[WORDING]), [routing.REASON_WORDING]),
    "1.4": (finding("1.4", "Avalon", C.REPORTING, CT.ADDED, None, None, "January 1, 2027"),
            [routing.REASON_ADDED_REMOVED]),
    "2.1": (finding("2.1", "Calder", C.WAGES, CT.SUBSTANTIVE, "14.50", "15.50", "January 1, 2027"), []),
    "2.2": (finding("2.2", "Calder", C.FILING_DEADLINE, CT.SUBSTANTIVE, "30", "20", "January 1, 2027"),
            [routing.REASON_DEADLINE]),
    "2.3": (finding("2.3", "Calder", C.REPORTING, CT.SUBSTANTIVE, None, None, None),
            [routing.REASON_NO_DATE]),
    "3.3": (finding("3.3", "Meridian", C.FILING_DEADLINE, CT.SUBSTANTIVE, "20", "10", "To be determined"),
            [routing.REASON_UNCLEAR_DATE]),
}


def route(f, **kw):
    return routing.route(f, **{"trusted": True, "jurisdictions": JURISDICTIONS, **kw})


def test_rule_passes_exactly_the_candidates_in_expected_md():
    ready = {s for s, (f, _) in EXPECTED.items() if route(f).ready}
    assert ready == {"1.1", "1.2", "2.1"}


@pytest.mark.parametrize("section", EXPECTED)
def test_route_label_and_reasons(section):
    f, reasons = EXPECTED[section]
    r = route(f)
    assert r.reasons == reasons
    assert r.label == (routing.READY_LABEL if r.ready else None)
    if r.ready:
        assert len(r.passed_conditions) == 8


def test_two_amounts_in_one_section_goes_to_the_reviewer():
    f = finding("1.1", "Avalon", C.WAGES, CT.SUBSTANTIVE, "16.00", "17.25", "November 1, 2026",
                flags=[Flag(name=FlagName.CONFLICTING_VALUES, reason="$16.50 and $17.00")])
    r = route(f)
    assert not r.ready and routing.REASON_TWO_AMOUNTS in r.reasons


def test_untrusted_source_failed_check_or_disagreeing_runs_go_to_the_reviewer():
    f = EXPECTED["1.1"][0]
    failed = [CheckResult(check="V1", passed=False, detail="quote missing"), *PASSED[1:]]
    for r in (route(f, trusted=False),
              route(f.model_copy(update={"check_results": failed})),
              route(f, runs_agree=False),
              route(f.model_copy(update={"check_results": []}))):
        assert not r.ready and routing.REASON_UNTRUSTED_OR_FAILED in r.reasons
    assert route(f, runs_agree=True).ready


def test_unknown_jurisdiction_goes_to_the_reviewer():
    r = route(EXPECTED["1.1"][0], jurisdictions=["Calder"])
    assert not r.ready and r.reasons


def test_pre_approve_is_the_configured_mode():
    assert routing.approval_mode(load_config()) is routing.ApprovalMode.PRE_APPROVE
    assert routing.approval_mode({}) is routing.ApprovalMode.PRE_APPROVE


@pytest.fixture
def conn(tmp_path):
    return db.connect(tmp_path / "maya.db")


def test_ready_finding_stays_pending_until_signed_off(conn):
    f = EXPECTED["1.1"][0]
    r = route(f)
    assert db.current_status(conn, f.finding_id) is Status.PENDING and db.history(conn) == []
    routing.sign_off(conn, {f.finding_id: r}, "Dana")
    (row,) = db.history(conn)
    assert row.status is Status.APPROVED and row.decided_by == "Dana"
    assert row.comment == "; ".join(r.passed_conditions)


def test_sign_off_refuses_a_finding_that_is_not_ready_and_writes_nothing(conn):
    ok, bad = EXPECTED["1.1"][0], EXPECTED["2.2"][0]
    with pytest.raises(ValueError, match="not ready"):
        routing.sign_off(conn, {ok.finding_id: route(ok), bad.finding_id: route(bad)}, "Dana")
    assert db.history(conn) == []


def test_sign_off_refuses_a_finding_already_decided_and_a_reversal_adds_a_row(conn):
    f = EXPECTED["1.1"][0]
    routes = {f.finding_id: route(f)}
    routing.sign_off(conn, routes, "Dana")
    with pytest.raises(ValueError, match="not pending"):
        routing.sign_off(conn, routes, "Dana")
    routing.decide(conn, f.finding_id, Status.DISMISSED, "Dana", "Wrong rate")
    assert [d.status for d in db.history(conn, f.finding_id)] == [Status.DISMISSED, Status.APPROVED]


def test_decide_dismiss_without_comment_is_refused(conn):
    with pytest.raises(ValueError):
        routing.decide(conn, "f1", Status.DISMISSED, "Dana", "  ")
    assert db.history(conn) == []
