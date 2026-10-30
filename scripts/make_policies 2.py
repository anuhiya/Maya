"""Rebuilds the fictional policy TXT and PDF files in data/ from one source, so every version stays consistent.

Run from anywhere: python scripts/make_policies.py
"""
import os
from fpdf import FPDF

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = "/usr/share/fonts/truetype/dejavu/"

MW = "Every employer shall pay each covered employee a wage of not less than {} per hour for all hours worked."
UI = "Every employer shall contribute {} of each covered employee's taxable wages to the Avalon Unemployment Insurance Fund."
PS1 = "Every employer shall furnish each employee, on every regular payday, a written or electronic pay statement showing gross wages, all deductions and net wages."
PS2 = "Every employer shall furnish each employee, on every regular payday, a written or electronic pay statement showing gross wages, all deductions, net wages and the hours worked at each rate of pay."
WN = "Every employer shall give each newly hired employee, on the first day of work, a written notice stating the employee's hourly rate of pay and regular payday."
QR = "Every employer shall file the quarterly wage and contribution report with the Department within {} calendar days after the close of each calendar quarter."
AE = "Every employer shall report to the Department, {} each calendar year, the total earnings paid to and hours worked by each employee."
OT1 = "Every employer shall pay each non-exempt employee one and one-half times the employee's regular rate of pay for all hours worked in excess of 40 hours in a workweek."
OT2 = "For each hour worked beyond 40 hours in a single workweek, an employer must compensate a non-exempt employee at one and one-half times that employee's regular rate of pay."
NH = "Every employer shall report each newly hired or rehired employee to the Department within {} calendar days of the employee's first day of work."

J1, J26, J27, N26 = "January 1, 2026", "January 1, 2026", "January 1, 2027", "November 1, 2026"

def gov_sections(v):
    s = [
        ("1.1", "Minimum Wage", "Avalon", J26 if v == 1 else N26, MW.format("$16.00" if v == 1 else "$17.25")),
        ("1.2", "Unemployment Insurance Contribution Rate", "Avalon", J26 if v == 1 else J27, UI.format("2.7%" if v == 1 else "3.1%")),
        ("1.3", "Pay Statements", "Avalon", J26 if v == 1 else J27, PS1 if v == 1 else PS2),
    ]
    if v >= 2:
        s.append(("1.4", "Wage Notice at Hire", "Avalon", J27, WN))
    s += [
        ("2.1", "Minimum Wage", "Calder", J26 if v == 1 else J27, MW.format("$14.50" if v == 1 else "$15.50")),
        ("2.2", "Quarterly Wage Report Filing", "Calder", J26 if v == 1 else J27, QR.format("30" if v == 1 else "20")),
        ("2.3", "Annual Earnings Report", "Calder", J26 if v == 1 else None, AE.format("once" if v == 1 else "twice")),
        ("3.1", "Minimum Wage", "Meridian", J26 if v < 3 else J27, MW.format("$13.75" if v < 3 else "$15.00")),
        ("3.2", "Overtime Pay", "Meridian", J26, OT1 if v == 1 else OT2),
        ("3.3", "New Hire Reporting", "Meridian", J26 if v == 1 else "To be determined", NH.format("20" if v == 1 else "10")),
    ]
    return s

GOV_META = {
    1: ("PSB-2026-01", "July 1, 2026", "None. First consolidated bulletin."),
    2: ("PSB-2026-02", "October 15, 2026", "Bulletin PSB-2026-01, issued July 1, 2026, in full."),
    3: ("PSB-2026-03", "November 2, 2026", "Bulletin PSB-2026-02, issued October 15, 2026, in full."),
}

def gov_front(v):
    no, issued, sup = GOV_META[v]
    return [
        ("org", "REGIONAL DEPARTMENT OF LABOR"),
        ("sub", "Division of Wage and Payroll Standards"),
        ("sub", "100 Commonwealth Plaza, Harbor City"),
        ("gap", ""),
        ("title", f"PAYROLL STANDARDS BULLETIN {no}"),
        ("subtitle", "Payroll Rules for Employers in Avalon, Calder and Meridian"),
        ("gap", ""),
        ("meta", f"Bulletin number: {no}"),
        ("meta", f"Issued: {issued}"),
        ("meta", f"Supersedes: {sup}"),
        ("meta", "Authority: Regional Wage and Payroll Standards Act, Title IV"),
        ("meta", "Applies to: every employer with employees whose work location is in Avalon, Calder or Meridian"),
        ("meta", "Approved by: Director, Division of Wage and Payroll Standards"),
        ("meta", "Employer helpline: 555-0142, weekdays 8:30 AM to 5:00 PM"),
        ("gap", ""),
        ("notice", "NOTICE: This is a synthetic document created for a software prototype. The Regional Department of Labor, the Act and the jurisdictions named here are fictional. It is not a real law, regulation or legal advice."),
        ("gap", ""),
        ("head", "PURPOSE AND USE"),
        ("para", "This bulletin states the payroll rules in force for each jurisdiction. Rules for Avalon appear in sections numbered 1, rules for Calder in sections numbered 2 and rules for Meridian in sections numbered 3. Each rule takes effect on the effective date shown with it. Where a rule shows no effective date, or a date that is not yet set, employers should contact the Division before changing payroll."),
        ("gap", ""),
        ("head", "WORK LOCATION"),
        ("para", "Each rule applies according to the jurisdiction where the work is performed, not where the employer's office is or where the employee lives. For an employee who works from home, the home is the work location. For an employee who works in more than one jurisdiction in the same workweek, the employer shall pay each hour worked at no less than the minimum wage of the jurisdiction where that hour is worked."),
        ("gap", ""),
        ("head", "RULES"),
    ]

COMPANY_SECTIONS = [
    ("1.1", "Pay Schedule", "Avalon", J26, "The company shall pay each employee on the weekly, biweekly or semimonthly schedule stated in the employee's offer letter."),
    ("1.2", "Overtime Approval", "Avalon", J26, "Hourly employees must obtain written approval from their manager before working more than 40 hours in a workweek."),
    ("2.1", "Pay Schedule", "Calder", J26, "The company shall pay each employee on the weekly, biweekly or semimonthly schedule stated in the employee's offer letter."),
    ("2.2", "Timekeeping", "Calder", J26, "Hourly employees must record their start and end times in the company time system on every working day."),
    ("3.1", "Pay Schedule", "Meridian", J26, "The company shall pay each employee on the weekly, biweekly or semimonthly schedule stated in the employee's offer letter."),
    ("3.2", "Contractor Payments", "Meridian", J26, "The company shall pay each independent contractor within 30 calendar days after receiving an approved invoice."),
]

COMPANY_FRONT = [
    ("org", "LARKSPUR SUPPLY CO."),
    ("sub", "Human Resources and Payroll"),
    ("gap", ""),
    ("title", "EMPLOYEE PAY POLICY: LOCATION SUPPLEMENTS"),
    ("subtitle", "Policy HR-PAY-04"),
    ("gap", ""),
    ("meta", "Policy number: HR-PAY-04"),
    ("meta", "Policy owner: Payroll Manager"),
    ("meta", "Approved by: Chief Financial Officer"),
    ("meta", "Last reviewed: October 1, 2026"),
    ("meta", "Next review: April 1, 2027"),
    ("meta", "Applies to: all employees and contractors at company locations in Avalon, Calder and Meridian"),
    ("gap", ""),
    ("notice", "NOTICE: This is a synthetic document created for a software prototype. Larkspur Supply Co. is a fictional company."),
    ("gap", ""),
    ("head", "PURPOSE AND USE"),
    ("para", "This policy sets the company's own pay practices at each location. Where this policy and the law differ, the law applies. Questions go to the Payroll Manager."),
    ("gap", ""),
    ("head", "REMOTE AND HYBRID WORK"),
    ("para", "Every employee has one office location and one work arrangement: onsite, hybrid or remote. For remote employees, the work location for pay purposes is the approved home address. Hybrid employees who work in two jurisdictions record their primary work location and the second jurisdiction in the payroll system. The company pays a hybrid employee at least the higher of the two minimum wages for all hours worked, so that no hour is underpaid. A change of home address or work arrangement must be approved by the Payroll Manager before it takes effect."),
    ("gap", ""),
    ("head", "POLICY"),
]

def to_txt(front, sections):
    out = []
    for kind, text in front:
        out.append(text)
    for num, title, jur, date, rule in sections:
        out += ["", f"{num} {title}", f"Jurisdiction: {jur}"]
        if date:
            out.append(f"Effective Date: {date}")
        out.append(rule)
    return "\n".join(out) + "\n"

ACCENT = (31, 58, 96)

def to_pdf(front, sections, path):
    pdf = FPDF(format="Letter")
    serif = "Times"  # built-in font, works on any computer
    if os.path.exists(FONT_DIR + "DejaVuSerif.ttf"):
        serif = "Serif"
        pdf.add_font("Serif", "", FONT_DIR + "DejaVuSerif.ttf")
        pdf.add_font("Serif", "B", FONT_DIR + "DejaVuSerif-Bold.ttf")
        pdf.add_font("Serif", "I", FONT_DIR + "DejaVuSerif-Italic.ttf")
    pdf.set_margins(22, 20, 22)
    pdf.set_auto_page_break(True, 20)
    pdf.add_page()
    W = pdf.w - 44
    for kind, text in front:
        if kind == "org":
            pdf.set_font(serif, "B", 15); pdf.set_text_color(*ACCENT)
            pdf.multi_cell(W, 7, text, align="C", new_x="LMARGIN", new_y="NEXT")
        elif kind == "sub":
            pdf.set_font(serif, "", 10); pdf.set_text_color(60, 60, 60)
            pdf.multi_cell(W, 5, text, align="C", new_x="LMARGIN", new_y="NEXT")
        elif kind == "title":
            y = pdf.get_y(); pdf.set_draw_color(*ACCENT); pdf.set_line_width(0.6)
            pdf.line(22, y, pdf.w - 22, y); pdf.ln(3)
            pdf.set_font(serif, "B", 13); pdf.set_text_color(20, 20, 20)
            pdf.multi_cell(W, 7, text, align="C", new_x="LMARGIN", new_y="NEXT")
        elif kind == "subtitle":
            pdf.set_font(serif, "I", 11); pdf.set_text_color(40, 40, 40)
            pdf.multi_cell(W, 6, text, align="C", new_x="LMARGIN", new_y="NEXT")
            y = pdf.get_y() + 2; pdf.line(22, y, pdf.w - 22, y); pdf.ln(3)
        elif kind == "meta":
            pdf.set_font(serif, "", 9.5); pdf.set_text_color(30, 30, 30)
            pdf.multi_cell(W, 5, text, new_x="LMARGIN", new_y="NEXT")
        elif kind == "notice":
            pdf.set_font(serif, "I", 9); pdf.set_text_color(120, 40, 30)
            pdf.multi_cell(W, 4.6, text, border=1, padding=2, new_x="LMARGIN", new_y="NEXT")
        elif kind == "head":
            pdf.set_font(serif, "B", 10.5); pdf.set_text_color(*ACCENT)
            pdf.multi_cell(W, 6, text, new_x="LMARGIN", new_y="NEXT")
        elif kind == "para":
            pdf.set_font(serif, "", 10); pdf.set_text_color(30, 30, 30)
            pdf.multi_cell(W, 5.2, text, new_x="LMARGIN", new_y="NEXT")
        elif kind == "gap":
            pdf.ln(3)
    for num, title, jur, date, rule in sections:
        if pdf.get_y() > pdf.h - 40:
            pdf.add_page()
        pdf.ln(3)
        pdf.set_font(serif, "B", 11); pdf.set_text_color(20, 20, 20)
        pdf.multi_cell(W, 6, f"{num} {title}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(serif, "", 9.5); pdf.set_text_color(70, 70, 70)
        pdf.multi_cell(W, 5, f"Jurisdiction: {jur}", new_x="LMARGIN", new_y="NEXT")
        if date:
            pdf.multi_cell(W, 5, f"Effective Date: {date}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(serif, "", 10.5); pdf.set_text_color(20, 20, 20)
        pdf.multi_cell(W, 5.6, rule, new_x="LMARGIN", new_y="NEXT")
    pdf.output(path)

def out(*parts):
    path = os.path.join(ROOT, "data", *parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


if __name__ == "__main__":
    for v in (1, 2, 3):
        text = to_txt(gov_front(v), gov_sections(v))
        if v < 3:
            for folder in ("policies", "policy_site"):
                open(out(folder, f"gov_rules_v{v}.txt"), "w").write(text)
            to_pdf(gov_front(v), gov_sections(v), out("policies", f"gov_rules_v{v}.pdf"))
        else:
            open(out("policy_site", "_unpublished", "gov_rules_v3.txt"), "w").write(text)
            to_pdf(gov_front(v), gov_sections(v), out("policy_site", "_unpublished", "gov_rules_v3.pdf"))
    for v in (1, 2):
        open(out("company_policies", f"company_pay_policy_v{v}.txt"), "w").write(to_txt(COMPANY_FRONT, COMPANY_SECTIONS))
    to_pdf(COMPANY_FRONT, COMPANY_SECTIONS, out("company_policies", "company_pay_policy.pdf"))
    print("Rebuilt the policy files in data/")
