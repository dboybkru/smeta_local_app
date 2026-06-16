from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import current_org, require_active
from app.auth.models import User
from app.core.db import get_db
from app.jobs import schemas
from app.jobs.models import Job

router = APIRouter(prefix="/api", tags=["jobs"])


@router.get("/jobs/{job_id}", response_model=schemas.JobOut)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
    org: int = Depends(current_org),
):
    job = db.get(Job, job_id)
    if job is None or job.org_id != org:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return job
