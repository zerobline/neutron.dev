from fastapi import APIRouter, HTTPException
from app.services.template_service import get_templates, get_template

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("")
def list_templates():
    return get_templates()


@router.get("/{template_id}")
def get_template_by_id(template_id: str):
    template = get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template
