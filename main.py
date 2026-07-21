from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncpg
import os
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL")
# This grabs your secret key from Render environment variables
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "wealthlens-default-secret")

# --- Security Middleware ---
@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    # Allow CORS preflight and documentation paths to pass through freely
    if request.method == "OPTIONS" or request.url.path in ["/", "/docs", "/openapi.json"]:
        return await call_next(request)
    
    # Protect all routes starting with /api/
    if request.url.path.startswith("/api/"):
        client_key = request.headers.get("x-api-key")
        if client_key != APP_SECRET_KEY:
            return JSONResponse(
                status_code=401, 
                content={"detail": "Unauthorized: Invalid or missing API Key"}
            )
            
    return await call_next(request)

# --- Pydantic Models ---
class NewAccount(BaseModel):
    name: str
    type: str  # 'Bank Account' or 'Credit Card'
    balance: float
    credit_limit: float = 0.0
    account_number: str = ""

class NewTransaction(BaseModel):
    account_id: int
    type: str  # 'income', 'expense', 'payment'
    amount: float
    description: str
    source_account_id: Optional[int] = None

# --- Endpoints ---
@app.get("/api/dashboard")
async def get_dashboard():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        accounts = await conn.fetch("SELECT * FROM accounts ORDER BY id")
        
        current_month = datetime.now().replace(day=1, hour=0, minute=0, second=0)
        monthly_spend = await conn.fetchval(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'expense' AND created_at >= $1", 
            current_month
        )

        total_cash = sum(acc['balance'] for acc in accounts if acc['type'] == 'bank')
        total_cc_due = sum(acc['balance'] for acc in accounts if acc['type'] == 'credit_card')
        net_worth = total_cash - total_cc_due

        return {
            "net_worth": net_worth,
            "total_cash": total_cash,
            "total_cc_due": total_cc_due,
            "monthly_spend": monthly_spend,
            "accounts": [dict(acc) for acc in accounts]
        }
    finally:
        await conn.close()

@app.post("/api/accounts")
async def add_account(account: NewAccount):
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        db_type = 'bank' if 'Bank' in account.type else 'credit_card'
        await conn.execute(
            "INSERT INTO accounts (name, type, balance, credit_limit, account_number) VALUES ($1, $2, $3, $4, $5)",
            account.name, db_type, account.balance, account.credit_limit, account.account_number
        )
        return {"status": "success"}
    finally:
        await conn.close()

@app.post("/api/transactions")
async def add_transaction(tx: NewTransaction):
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO transactions (account_id, type, amount, description) VALUES ($1, $2, $3, $4)",
                tx.account_id, tx.type, tx.amount, tx.description
            )
            
            if tx.type == 'expense':
                await conn.execute(
                    "UPDATE accounts SET balance = balance + $1 WHERE id = $2 AND type = 'credit_card'",
                    tx.amount, tx.account_id
                )
                await conn.execute(
                    "UPDATE accounts SET balance = balance - $1 WHERE id = $2 AND type = 'bank'",
                    tx.amount, tx.account_id
                )
            elif tx.type == 'income':
                await conn.execute(
                    "UPDATE accounts SET balance = balance + $1 WHERE id = $2", tx.amount, tx.account_id
                )
            elif tx.type == 'payment':
                await conn.execute(
                    "UPDATE accounts SET balance = balance - $1 WHERE id = $2", tx.amount, tx.account_id
                )
                if tx.source_account_id:
                    await conn.execute(
                        "UPDATE accounts SET balance = balance - $1 WHERE id = $2", tx.amount, tx.source_account_id
                    )

        return {"status": "success"}
    finally:
        await conn.close()
