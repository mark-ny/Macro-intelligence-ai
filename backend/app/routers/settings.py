from fastapi import APIRouter

from app.models.schemas import ModuleStatus

router = APIRouter()


@router.get("/status", response_model=ModuleStatus)
async def status():
    """Settings has no backend endpoints by design: user_settings is
    protected by RLS (auth.uid() = user_id), so the frontend reads and
    writes it directly with the user's own session — see
    frontend/src/app/settings/page.tsx. Routing it through this
    service-role backend would add a JWT-passthrough step for no benefit
    RLS doesn't already provide."""
    return ModuleStatus(
        module="Settings",
        status="implemented (client-direct against Supabase, RLS-scoped)",
        implemented=True,
    )
