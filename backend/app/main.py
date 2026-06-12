from fastapi import FastAPI

from app.auth.admin_router import router as admin_router
from app.auth.router import router as auth_router

app = FastAPI(title="SmetaApp API")
app.include_router(auth_router)
app.include_router(admin_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
