from fastapi import APIRouter
from app.api.routes import (
    auth,
    users,
    departments,
    analysis,
    audio,
    complaints,
    officers,
    admin,
    notifications,
    ivr,
    assistant,
    voice_register,
    voice,
    ai
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(departments.router)
api_router.include_router(analysis.router)
api_router.include_router(audio.router)
api_router.include_router(ai.router)
api_router.include_router(complaints.router)
api_router.include_router(officers.router)
api_router.include_router(admin.router)
api_router.include_router(notifications.router)
api_router.include_router(ivr.router)
api_router.include_router(assistant.router)
api_router.include_router(voice_register.router)
api_router.include_router(voice.router)
