import json

import uvicorn
from fastapi import FastAPI, Header, Request, HTTPException

from a2a.types import StreamResponse

HOST = "127.0.0.1"
PORT = 3000

app = FastAPI()


@app.post("/webhook")
async def webhook(
    request : Request,
    
):
    