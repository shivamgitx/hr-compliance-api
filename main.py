"""FastAPI service exposing HR transaction policy compliance (rules R01-R18)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

from compliance import ComplianceEngine

BASE_DIR = Path(__file__).resolve().parent
engine = ComplianceEngine(BASE_DIR / "data", BASE_DIR / "policy_rules.md")

app = FastAPI(
    title="HR Compliance API",
    description="Policy-compliance checking over HR transactions (rules R01-R18).",
    version="1.0.0",
)


@app.get("/")
def root() -> dict:
    return {
        "service": "hr-compliance-api",
        "version": app.version,
        "rules": len(engine.rules),
        "transactions": len(engine.transactions),
        "employees": len(engine.employees),
        "violations": len(engine.violations),
        "endpoints": ["/health", "/rules", "/summary", "/violations", "/transactions", "/transactions/{txn_id}", "/employees/{employee_id}/violations"],
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/rules")
def rules() -> list[dict]:
    return [engine.rules[rid] for rid in sorted(engine.rules)]


@app.get("/summary")
def summary() -> dict:
    severity_totals: dict[str, int] = {}
    for v in engine.violations:
        sev = engine.rules[v.rule_id]["severity"]
        severity_totals[sev] = severity_totals.get(sev, 0) + 1
    return {
        "transactions": len(engine.transactions),
        "violating_transactions": len(engine.violations_by_txn),
        "violations": len(engine.violations),
        "by_severity": severity_totals,
        "by_rule": engine.rule_stats(),
    }


@app.get("/violations")
def violations(
    rule_id: str | None = Query(None, description="Filter by rule id, e.g. R01"),
    severity: str | None = Query(None, description="High | Medium | Low"),
    txn_type: str | None = Query(None),
    employee_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    if rule_id and rule_id.upper() not in engine.rules:
        raise HTTPException(status_code=404, detail=f"Unknown rule_id {rule_id}")
    if severity and severity.capitalize() not in ("High", "Medium", "Low"):
        raise HTTPException(status_code=422, detail="severity must be High, Medium or Low")

    txn_type_map = {t["txn_id"]: t["txn_type"] for t in engine.transactions}
    employee_map = {t["txn_id"]: t["employee_id"] for t in engine.transactions}
    results = []
    for v in engine.violations:
        rule = engine.rules[v.rule_id]
        if rule_id and v.rule_id != rule_id.upper():
            continue
        if severity and rule["severity"] != severity.capitalize():
            continue
        if txn_type and txn_type_map[v.txn_id] != txn_type:
            continue
        if employee_id and employee_map[v.txn_id] != employee_id:
            continue
        results.append(v.enriched(engine.rules))

    return {
        "total": len(results),
        "offset": offset,
        "limit": limit,
        "items": results[offset : offset + limit],
    }


@app.get("/transactions")
def list_transactions(
    txn_type: str | None = Query(None),
    employee_id: str | None = Query(None),
    violating_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    selected = []
    for t in engine.transactions:
        if txn_type and t["txn_type"] != txn_type:
            continue
        if employee_id and t["employee_id"] != employee_id:
            continue
        if violating_only and t["txn_id"] not in engine.violations_by_txn:
            continue
        selected.append(t)
    return {
        "total": len(selected),
        "offset": offset,
        "limit": limit,
        "items": [engine.transaction_view(t) for t in selected[offset : offset + limit]],
    }


@app.get("/transactions/{txn_id}")
def get_transaction(txn_id: str) -> dict:
    t = engine.txn_by_id.get(txn_id)
    if t is None:
        raise HTTPException(status_code=404, detail=f"Unknown transaction {txn_id}")
    return engine.transaction_view(t)


@app.get("/employees/{employee_id}/violations")
def employee_violations(
    employee_id: str,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    if employee_id not in engine.employees:
        raise HTTPException(status_code=404, detail=f"Unknown employee {employee_id}")
    found = engine.violations_by_employee.get(employee_id, [])
    items = [v.enriched(engine.rules) for v in found[offset : offset + limit]]
    return {
        "employee_id": employee_id,
        "total": len(found),
        "offset": offset,
        "limit": limit,
        "items": items,
    }
