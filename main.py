#!/usr/bin/env python3
"""
Tunnel Server - Entry Point
Run with: python main.py
Or: uvicorn main:app --reload
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
