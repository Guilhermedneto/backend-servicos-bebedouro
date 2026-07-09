import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.errors import AppError, error_body
from app.core.security import hash_password
from app.domain.entities import Role, new_user_doc
from app.infrastructure.blob_storage import init_blob_storage
from app.infrastructure.cosmos_db import init_cosmos
from app.infrastructure.repositories import CosmosUserRepository
from app.presentation.routers import admin, auth, categories, providers, search

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("servicos-bebedouro")
settings = get_settings()


def seed_admin() -> None:
    settings = get_settings()
    if not settings.admin_password:
        logger.warning("ADMIN_PASSWORD não definido — seed do administrador ignorado.")
        return
    users = CosmosUserRepository()
    if users.find_by_email(settings.admin_email):
        return
    doc = new_user_doc(
        settings.admin_name, settings.admin_email, hash_password(settings.admin_password), Role.ADMIN
    )
    users.create(doc)
    logger.info("Conta de administrador criada: %s", settings.admin_email)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_cosmos()
    init_blob_storage()
    seed_admin()
    yield


app = FastAPI(
    title="Serviços Bebedouro API",
    description="Plataforma de divulgação de prestadores de serviços e comerciantes de Bebedouro/SP.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=()"

    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if request.url.scheme == "https" or forwarded_proto.lower() == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code, content=error_body(exc.code, exc.message, exc.details)
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    details = [
        {"field": ".".join(str(loc) for loc in err["loc"] if loc != "body"), "message": err["msg"]}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=error_body("VALIDATION_FAILED", "Dados inválidos na requisição.", details),
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Erro não tratado em %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=error_body("INTERNAL_ERROR", "Erro interno do servidor."),
    )


app.include_router(auth.router)
app.include_router(providers.router)
app.include_router(categories.router)
app.include_router(admin.router)
app.include_router(search.router)
