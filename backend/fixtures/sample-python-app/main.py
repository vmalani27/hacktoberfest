import os
from fastapi import FastAPI

app = FastAPI(title="Sample Python Microservice")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/app_db")
PORT = int(os.getenv("PORT", "8000"))

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "sample-python-app",
        "configured_database": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else "local"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
