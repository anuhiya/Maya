"""Employee matching rules R1 to R4 (B3). Takes Finding objects, never calls the AI."""
from decimal import Decimal

from maya.cost import implied_hourly_rate, weekly_increase
from maya.models import (Category, ChangeType, Employee, EmploymentType, Finding, Flag,
                         FlagName, ImpactResult, ImpactRow)
from maya.site import load_config

HOURLY = (EmploymentType.HOURLY_FULL_TIME, EmploymentType.HOURLY_PART_TIME)
RULE_BY_CATEGORY = {Category.WAGES: "R1", Category.TAX_RATE: "R2",
                    Category.FILING_DEADLINE: "R3", Category.REPORTING: "R4"}


def match_finding(finding: Finding, employees: list[Employee], cfg: dict | None = None) -> list[ImpactRow]:
    """One ImpactRow for every employee whose work-location jurisdiction is the finding's."""
    cfg = cfg or load_config()
    in_place = [e for e in employees if e.jurisdiction == finding.jurisdiction]

    if finding.change_type is ChangeType.WORDING_ONLY:
        return [_row(finding, e, "none", ImpactResult.NOT_AFFECTED,
                     "wording change only, no operational impact") for e in in_place]
    if finding.category is Category.UNCLEAR:
        return [_row(finding, e, "none", *_unclear(e)) for e in in_place]
    if finding.category is Category.WAGES:
        return [_wage_row(finding, e) for e in in_place]
    if finding.category is Category.REPORTING and _is_new_hire(finding, cfg):
        return [_row(finding, e, "R4", ImpactResult.NOT_AFFECTED,
                     "applies to future hires only, no current employee") for e in in_place]
    return [_row(finding, e, RULE_BY_CATEGORY[finding.category], *_covered(finding, e))
            for e in in_place]


def _row(finding: Finding, e: Employee, rule: str, result: ImpactResult, reason: str,
         minimum: Decimal | None = None, increase: Decimal | None = None,
         calc: str = "", flags: list[Flag] | None = None) -> ImpactRow:
    return ImpactRow(
        finding_id=finding.finding_id, employee_id=e.employee_id, jurisdiction=e.jurisdiction,
        employment_type=e.employment_type, hourly_wage=e.hourly_wage, weekly_hours=e.weekly_hours,
        rule_id=rule, result=result, reason=reason, new_minimum=minimum, weekly_increase=increase,
        calculation=calc, timing=finding.timing, flags=flags or [])


def _unclear(e: Employee) -> tuple[ImpactResult, str]:
    if e.employment_type is EmploymentType.CONTRACTOR:
        return ImpactResult.EXCLUDED, "contractor, not an employee of the company"
    return ImpactResult.NEEDS_REVIEW, "category unclear, a reviewer decides"


def _covered(finding: Finding, e: Employee) -> tuple[ImpactResult, str]:
    """R2, R3 and R4 (non new-hire): every non-contractor in the jurisdiction, no estimate."""
    if e.employment_type is EmploymentType.CONTRACTOR:
        return ImpactResult.EXCLUDED, "contractor, not covered by this rule"
    what = {Category.TAX_RATE: "employer tax rate applies to this employee's wages, no dollar estimate",
            Category.FILING_DEADLINE: "included in the employer's filing, no pay change",
            Category.REPORTING: "covered by this reporting rule, no pay change"}[finding.category]
    return ImpactResult.MATCHED_NO_ESTIMATE, what


def _is_new_hire(finding: Finding, cfg: dict) -> bool:
    terms = [t.lower() for t in (cfg.get("matching") or {}).get("new_hire_terms", [])]
    text = " ".join(filter(None, (finding.new_rule, finding.old_rule,
                                  finding.new_excerpt, finding.old_excerpt))).lower()
    return any(t in text for t in terms)


def _wage_row(finding: Finding, e: Employee) -> ImpactRow:
    """R1: hourly staff below the new minimum are affected; exempt and contractors are excluded."""
    minimum_known = shown = finding.new_value
    if minimum_known is None and e.employment_type in HOURLY:
        return _row(finding, e, "R1", ImpactResult.MATCHED_NO_ESTIMATE,
                    "wage rule has no stated minimum, cannot estimate")

    if e.employment_type is EmploymentType.CONTRACTOR:
        if minimum_known is not None and e.hourly_wage < minimum_known:
            reason = (f"Classification warning: contractor paid ${e.hourly_wage:.2f} an hour, below the "
                      f"new minimum ${minimum_known:.2f}; check whether they are correctly classified")
            flag = Flag(name=FlagName.CLASSIFICATION_WARNING, reason=reason)
            return _row(finding, e, "R1", ImpactResult.EXCLUDED, reason, shown, flags=[flag])
        return _row(finding, e, "R1", ImpactResult.EXCLUDED, "contractor, minimum wage does not apply", shown)

    if e.employment_type is EmploymentType.SALARIED_EXEMPT:
        rate = implied_hourly_rate(e.annual_salary) if e.annual_salary else e.hourly_wage
        reason = "salaried exempt, minimum wage does not apply"
        if minimum_known is not None and rate < minimum_known:
            reason += f"; implied hourly rate ${rate:.2f} is below the new minimum ${minimum_known:.2f}"
        return _row(finding, e, "R1", ImpactResult.EXCLUDED, reason, shown)

    if e.hourly_wage >= minimum_known:
        return _row(finding, e, "R1", ImpactResult.NOT_AFFECTED,
                    f"${e.hourly_wage:.2f} is at or above the new minimum ${minimum_known:.2f}", shown)
    amount, calc = weekly_increase(e.hourly_wage, e.weekly_hours, minimum_known)
    return _row(finding, e, "R1", ImpactResult.AFFECTED,
                f"${e.hourly_wage:.2f} is below the new minimum ${minimum_known:.2f}",
                shown, amount, calc)
