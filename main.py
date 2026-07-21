from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import asyncpg
from pydantic import BaseModel

app = FastAPI(title="WealthLens API")

# Allow your PWA frontend to talk to this API securely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Change this to your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Render and Hugging Face will securely inject this variable
DATABASE_URL = os.getenv("DATABASE_URL")

@app.get("/")
async def root():
    return {"status": "WealthLens API is Live"}

@app.get("/api/accounts")
async def get_accounts():
    '''Fetches all bank and credit card accounts from Supabase'''
    if not DATABASE_URL:
        return {"error": "DATABASE_URL environment variable is missing."}
    
    conn = await asyncpg.connect(DATABASE_URL)
    # Fetch data based on the schema we created earlier
    rows = await conn.fetch("SELECT id, name, type, balance, monthly_limit FROM accounts")
    await conn.close()
    
    return [dict(row) for row in rows]

# Add more endpoints (e.g., POST /api/transactions) as you build out the app!

from pydantic import BaseModel

# Define the shape of the incoming data
class NewAccount(BaseModel):
    name: str
    type: str
    balance: float

# Create the route to accept new accounts
@app.post("/api/accounts")
async def add_account(account: NewAccount):
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Convert 'Bank Account' or 'Credit Card' to your database format
        db_type = 'bank' if 'Bank' in account.type else 'credit_card'
        
        await conn.execute(
            "INSERT INTO accounts (name, type, balance) VALUES ($1, $2, $3)",
            account.name, db_type, account.balance
        )
        return {"message": "Account added successfully!"}
    finally:
        await conn.close()
