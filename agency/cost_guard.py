"""Fail-closed cost gate for future paid model/worker integrations.

This gate estimates and reserves a user-specified upper bound in USD.
It deliberately makes NO LLM calls and NEVER spends money. The future
executor must call this service before every billable action, and must
commit/release reservations on completion, including unexpected failures.
"""
import os
import uuid
from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

ZERO=Decimal("0")
CENT=Decimal("0.01")

def dollars(value):
    try:
        result=Decimal(str(value))
        if not result.is_finite() or result < ZERO or result.as_tuple().exponent < -2:
            raise ValueError("Amount must be positive USD rounded to cents")
        return result.quantize(CENT)
    except (InvalidOperation,ValueError,TypeError):
        raise HTTPException(422,"Invalid dollar amount")

class Reserve(BaseModel):
    task_id: str=Field(min_length=1,max_length=120)
    max_cost_usd: str=Field(min_length=1,max_length=16)
    category: Literal["LLM","VIDEO","SANDBOX","OTHER"]
    idempotency_key: str=Field(min_length=12,max_length=120)

def register_budget(app,database,auth,now):
    router=APIRouter(prefix="/api/v1",dependencies=[Depends(auth)])
    with database() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS cost_reservations(
            id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL,
            task_id TEXT NOT NULL, category TEXT NOT NULL,
            max_cents INTEGER NOT NULL, status TEXT NOT NULL,
            date_utc TEXT NOT NULL, created_at TEXT NOT NULL)""")
    def limit(name):
        val=os.getenv(name,"0")
        try:
            number=dollars(val)
        except HTTPException:
            raise HTTPException(503,"Invalid cost policy")
        return int(number*100)

    @router.get("/cost-policy")
    def policy():
        # Strictly opt-in: defaults to disabled and $0.
        enabled=os.getenv("AGENCY_PAID_OPERATIONS_ENABLED","false").lower()=="true"
        return {"enabled":enabled,"daily_limit_usd":str(Decimal(limit("AGENCY_DAILY_BUDGET_USD"))/100),
                "task_limit_usd":str(Decimal(limit("AGENCY_TASK_BUDGET_USD"))/100),
                "charging_enabled_by_this_endpoint":False,
                "mode":"REVIEW_ONLY"}

    @router.post("/cost-reservations",status_code=201)
    def reserve(body:Reserve):
        cost=int(dollars(body.max_cost_usd)*100)
        max_daily=limit("AGENCY_DAILY_BUDGET_USD")
        max_task=limit("AGENCY_TASK_BUDGET_USD")
        if os.getenv("AGENCY_PAID_OPERATIONS_ENABLED","false").lower()!="true" or max_daily==0 or max_task==0:
            raise HTTPException(403,"Paid operations disabled by zero-budget policy")
        if cost==0 or cost>max_daily or cost>max_task:
            raise HTTPException(403,"Cost exceeds per-task or daily limit")
        stamp=now()
        date=stamp[:10]
        with database() as db:
            # Single-writer reservation transaction to prevent concurrent overspend.
            db.execute("BEGIN IMMEDIATE")
            existing=db.execute("SELECT * FROM cost_reservations WHERE idempotency_key=?",
                                (body.idempotency_key,)).fetchone()
            if existing:
                if existing["task_id"]!=body.task_id or existing["max_cents"]!=cost or existing["category"]!=body.category:
                    raise HTTPException(409,"Idempotency key conflict")
                return {"id":existing["id"],"status":existing["status"],
                        "reserved_usd":str(Decimal(existing["max_cents"])/100),"idempotent":True}
            used=db.execute("""SELECT COALESCE(SUM(max_cents),0) AS used
                              FROM cost_reservations WHERE date_utc=? AND status='RESERVED'""",(date,)).fetchone()["used"]
            if used+cost>max_daily:
                raise HTTPException(403,"Daily reserved budget exhausted")
            rid=str(uuid.uuid4())
            db.execute("INSERT INTO cost_reservations VALUES(?,?,?,?,?,?,?,?)",
                       (rid,body.idempotency_key,body.task_id,body.category,cost,"RESERVED",date,stamp))
        return {"id":rid,"status":"RESERVED","reserved_usd":str(Decimal(cost)/100),
                "idempotent":False,"external_call_executed":False}

    app.include_router(router)
