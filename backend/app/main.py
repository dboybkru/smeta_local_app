from fastapi import FastAPI

from app.auth.admin_router import router as admin_router
from app.auth.router import router as auth_router
from app.catalog.router import router as catalog_router
from app.estimates.router import router as estimates_router
from app.profile.router import router as profile_router
from app.export.router import router as export_router
from app.proposals.router import router as proposals_router
from app.publiclinks.router import router as publiclinks_router
from app.publiclinks.public_router import router as public_page_router
from app.ai.router import router as ai_router

app = FastAPI(title="SmetaApp API")
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(catalog_router)
app.include_router(estimates_router)
app.include_router(profile_router)
app.include_router(proposals_router)
app.include_router(export_router)
app.include_router(publiclinks_router)
app.include_router(public_page_router)
app.include_router(ai_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
