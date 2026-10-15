from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.deps import get_db_path
from api.routers import analytics, auth, catalog, customers, dashboard, pos, suppliers, users
from core.auth import seed_default_users
from core.db import init_db


def create_app():
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        db_path = get_db_path()
        init_db(db_path)
        seed_default_users(db_path)
        yield

    app = FastAPI(title="إدارة المتجر برو", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(catalog.router)
    app.include_router(customers.router)
    app.include_router(suppliers.router)
    app.include_router(pos.router)
    app.include_router(analytics.router)
    app.include_router(users.router)
    return app


app = create_app()
