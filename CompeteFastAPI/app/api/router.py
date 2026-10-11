"""Root API router combining all endpoint modules."""
from fastapi import APIRouter
from app.api.endpoints import users, compare

api_router = APIRouter()
api_router.include_router(users.router)
api_router.include_router(compare.router)

