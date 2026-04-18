from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .... import models, schemas
from ....db import get_db
from ....services.optimizer_service import LayoutOptimizerService


router = APIRouter(prefix="/projects", tags=["projects"])
optimizer_service = LayoutOptimizerService()


@router.get("/{project_id}", response_model=schemas.ProjectSnapshotResponse)
def get_project(project_id: str, db: Session = Depends(get_db)) -> schemas.ProjectSnapshotResponse:
    project = db.get(models.Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return optimizer_service.serialize_project(db, project)


@router.get("/{project_id}/bim-data-status", response_model=schemas.BimDataStatus)
def get_project_bim_data_status(
    project_id: str,
    db: Session = Depends(get_db),
) -> schemas.BimDataStatus:
    return optimizer_service.serialize_bim_data_status(db, project_id)


@router.put("/{project_id}/bim-data-status", response_model=schemas.BimDataStatus)
def upsert_project_bim_data_status(
    project_id: str,
    payload: schemas.BimDataStatusUpdateRequest,
    db: Session = Depends(get_db),
) -> schemas.BimDataStatus:
    return optimizer_service.upsert_bim_data_status(db, project_id, payload)


@router.put("/{project_id}", response_model=schemas.ProjectSnapshotResponse)
def upsert_project(
    project_id: str,
    payload: schemas.ProjectSnapshotRequest,
    db: Session = Depends(get_db),
) -> schemas.ProjectSnapshotResponse:
    project = optimizer_service.upsert_project_snapshot(db, project_id, payload)
    return optimizer_service.serialize_project(db, project)


@router.post("/{project_id}/optimize", response_model=schemas.OptimizeProjectResponse)
def optimize_project(
    project_id: str,
    payload: schemas.OptimizeProjectRequest,
    db: Session = Depends(get_db),
) -> schemas.OptimizeProjectResponse:
    project = optimizer_service.upsert_project_snapshot(db, project_id, payload)
    return optimizer_service.optimize_project(db, project, payload)
