"""Rule engine for the HR compliance challenge (rules R01-R18)."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

HIRE_DOCS = frozenset({"offer_letter", "id_copy", "medical_clearance", "degree_certificate"})
EXIT_DOCS = frozenset({"resignation_letter", "clearance_form"})

R18_TYPES = frozenset({"Pay Change", "Allowance Change", "Transfer", "Leave"})


def pay_change_limit(grade: int) -> int:
    if grade <= 4:
        return 2000
    if grade <= 6:
        return 4000
    return 8000


def allowance_cap(grade: int) -> int:
    if grade <= 4:
        return 1500
    if grade <= 6:
        return 3000
    if grade <= 8:
        return 6000
    return 10000


def _parse_ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def _parse_date(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def _docs(raw: str) -> frozenset[str]:
    return frozenset(d for d in raw.split("|") if d)


def load_rules(policy_path: Path) -> dict[str, dict[str, str]]:
    """Parse the rule table out of policy_rules.md."""
    rules: dict[str, dict[str, str]] = {}
    for line in policy_path.read_text().splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 5 or not cells[0].startswith("R") or not cells[0][1:].isdigit():
            continue
        rules[cells[0]] = {
            "rule_id": cells[0],
            "category": cells[1],
            "rule_text": cells[2],
            "severity": cells[3],
            "owner": cells[4],
        }
    return rules


@dataclass(frozen=True)
class Violation:
    txn_id: str
    rule_id: str
    message: str

    def enriched(self, rules: dict[str, dict[str, str]]) -> dict[str, Any]:
        rule = rules[self.rule_id]
        return {
            "txn_id": self.txn_id,
            "rule_id": self.rule_id,
            "category": rule["category"],
            "severity": rule["severity"],
            "owner": rule["owner"],
            "message": self.message,
        }


class ComplianceEngine:
    def __init__(self, data_dir: Path, policy_path: Path):
        self.rules = load_rules(policy_path)
        self.employees = self._load_employees(data_dir / "employees.csv")
        self.transactions = self._load_transactions(data_dir / "transactions.csv")
        self.violations = self._evaluate()
        self.violations_by_txn: dict[str, list[Violation]] = defaultdict(list)
        for v in self.violations:
            self.violations_by_txn[v.txn_id].append(v)
        self.txn_by_id = {t["txn_id"]: t for t in self.transactions}
        self.violations_by_employee: dict[str, list[Violation]] = defaultdict(list)
        for t in self.transactions:
            for v in self.violations_by_txn.get(t["txn_id"], []):
                self.violations_by_employee[t["employee_id"]].append(v)

    @staticmethod
    def _load_employees(path: Path) -> dict[str, dict[str, Any]]:
        employees: dict[str, dict[str, Any]] = {}
        with path.open(newline="") as fh:
            for row in csv.DictReader(fh):
                row["grade"] = int(row["grade"])
                row["exit_date"] = _parse_date(row["exit_date"])
                employees[row["employee_id"]] = row
        return employees

    @staticmethod
    def _load_transactions(path: Path) -> list[dict[str, Any]]:
        txns: list[dict[str, Any]] = []
        with path.open(newline="") as fh:
            for row in csv.DictReader(fh):
                row["amount"] = int(row["amount"])
                row["grade"] = int(row["grade"])
                row["submitted"] = _parse_ts(row["submitted_ts"])
                row["approved"] = _parse_ts(row["approved_ts"])
                row["submitted_date"] = row["submitted"].date()
                row["approved_date"] = row["approved"].date()
                row["effective_date"] = _parse_date(row["effective_date"])
                row["documents"] = _docs(row["documents_attached"])
                txns.append(row)
        return txns

    def _evaluate(self) -> list[Violation]:
        violations: list[Violation] = []

        dup_groups: dict[tuple[str, str, date], list[dict[str, Any]]] = defaultdict(list)
        for t in self.transactions:
            dup_groups[(t["employee_id"], t["txn_type"], t["effective_date"])].append(t)
        duplicate_ids: set[str] = set()
        for group in dup_groups.values():
            if len(group) > 1:
                earliest = min(group, key=lambda t: t["submitted"])
                duplicate_ids.update(t["txn_id"] for t in group if t is not earliest)

        for t in self.transactions:
            emp = self.employees[t["employee_id"]]
            grade = emp["grade"]
            txn_id = t["txn_id"]
            txn_type = t["txn_type"]
            requester = t["requester_id"]
            approver_1 = t["approver_1_id"]
            approver_2 = t["approver_2_id"]
            amount = t["amount"]
            effective = t["effective_date"]

            def add(rule_id: str, message: str) -> None:
                violations.append(Violation(txn_id=txn_id, rule_id=rule_id, message=message))

            # R01 - segregation of duties
            if requester == approver_1:
                add("R01", f"Requester {requester} is also the first approver")
            if requester and requester == approver_2:
                add("R01", f"Requester {requester} is also the second approver")

            # R02 - approvers must differ
            if approver_2 and approver_1 == approver_2:
                add("R02", f"First and second approver are the same person ({approver_1})")

            # R03 - first approver grade
            approver_1_grade = self.employees[approver_1]["grade"]
            if grade == 9:
                if approver_1_grade != 9:
                    add("R03", f"Employee is G9 but first approver {approver_1} is G{approver_1_grade}, not G9")
            elif approver_1_grade <= grade:
                add("R03", f"First approver {approver_1} (G{approver_1_grade}) is not above employee grade G{grade}")

            # R04 - pay change second-approver threshold
            if txn_type == "Pay Change":
                limit = pay_change_limit(grade)
                if amount > limit and not approver_2:
                    add("R04", f"Pay Change of AED {amount}/month exceeds the G{grade} threshold of AED {limit} but has no second approver")

                # R05 - very large pay change needs a G9 second approver
                if amount > 15000:
                    if not approver_2:
                        add("R05", f"Pay Change of AED {amount}/month exceeds AED 15,000 but has no second approver")
                    else:
                        a2_grade = self.employees[approver_2]["grade"]
                        if a2_grade != 9:
                            add("R05", f"Pay Change of AED {amount}/month exceeds AED 15,000 but second approver {approver_2} is G{a2_grade}, not G9")

            # R06 - allowance cap
            if txn_type == "Allowance Change":
                cap = allowance_cap(grade)
                if amount > cap:
                    add("R06", f"Allowance Change of AED {amount}/month exceeds the G{grade} cap of AED {cap}")

            # R07-R11 - required documents
            if txn_type == "Hire":
                missing = sorted(HIRE_DOCS - t["documents"])
                if missing:
                    add("R07", f"Hire is missing required documents: {', '.join(missing)}")
            elif txn_type == "Exit":
                missing = sorted(EXIT_DOCS - t["documents"])
                if missing:
                    add("R08", f"Exit is missing required documents: {', '.join(missing)}")
            elif txn_type == "Pay Change" and "approval_memo" not in t["documents"]:
                add("R09", "Pay Change is missing approval_memo")
            elif txn_type == "Allowance Change" and "justification_memo" not in t["documents"]:
                add("R09", "Allowance Change is missing justification_memo")
            elif txn_type == "Transfer" and "transfer_form" not in t["documents"]:
                add("R10", "Transfer is missing transfer_form")
            elif txn_type == "Leave":
                if "leave_form" not in t["documents"]:
                    add("R11", "Leave is missing leave_form")
                if amount > 30 and "medical_certificate" not in t["documents"]:
                    add("R11", f"Leave of {amount} days exceeds 30 days and is missing medical_certificate")

            # R12 - long leave needs a second approver
            if txn_type == "Leave" and amount > 30 and not approver_2:
                add("R12", f"Leave of {amount} days exceeds 30 days but has no second approver")

            # R13 - G8/G9 always need a second approver
            if grade in (8, 9) and not approver_2:
                add("R13", f"Employee at grade G{grade} requires a second approver but none is recorded")

            # R14 - backdating window
            if txn_type in ("Pay Change", "Allowance Change"):
                backdated_days = (t["approved_date"] - effective).days
                if backdated_days > 30:
                    add("R14", f"Effective date {effective} is {backdated_days} days before approval date {t['approved_date']} (max 30)")

            # R15 - hire/transfer approved on or before effective date
            if txn_type in ("Hire", "Transfer") and t["approved_date"] > effective:
                add("R15", f"Approved on {t['approved_date']}, after the effective date {effective}")

            # R16 - approval turnaround
            turnaround = (t["approved_date"] - t["submitted_date"]).days
            if turnaround > 10:
                add("R16", f"Approved {turnaround} days after submission (max 10)")

            # R17 - duplicates (later submission is the exception)
            if txn_id in duplicate_ids:
                add("R17", f"Duplicate: an earlier {txn_type} for employee {t['employee_id']} has the same effective date {effective}")

            # R18 - no effect after exit
            if txn_type in R18_TYPES and emp["exit_date"] and effective > emp["exit_date"]:
                add("R18", f"Effective date {effective} is after the employee's exit date {emp['exit_date']}")

        return violations

    def rule_stats(self) -> list[dict[str, Any]]:
        counts = Counter(v.rule_id for v in self.violations)
        return [
            {
                "rule_id": rid,
                "category": self.rules[rid]["category"],
                "severity": self.rules[rid]["severity"],
                "violations": counts.get(rid, 0),
            }
            for rid in sorted(self.rules)
        ]

    def transaction_view(self, t: dict[str, Any]) -> dict[str, Any]:
        emp = self.employees[t["employee_id"]]
        return {
            "txn_id": t["txn_id"],
            "txn_type": t["txn_type"],
            "employee_id": t["employee_id"],
            "employee_name": emp["full_name"],
            "grade": t["grade"],
            "department": t["department"],
            "amount": t["amount"],
            "amount_unit": t["amount_unit"],
            "effective_date": t["effective_date"].isoformat(),
            "requester_id": t["requester_id"],
            "approver_1_id": t["approver_1_id"],
            "approver_2_id": t["approver_2_id"] or None,
            "submitted_ts": t["submitted_ts"],
            "approved_ts": t["approved_ts"],
            "documents": sorted(t["documents"]),
            "employment_status": emp["employment_status"],
            "exit_date": emp["exit_date"].isoformat() if emp["exit_date"] else None,
            "violations": [v.enriched(self.rules) for v in self.violations_by_txn.get(t["txn_id"], [])],
        }
