from fastapi import APIRouter, Depends

from app.application.commands.auth import (
    LoginCommand,
    LoginHandler,
    LogoutCommand,
    LogoutHandler,
    RefreshTokenCommand,
    RefreshTokenHandler,
    RegisterProviderCommand,
    RegisterProviderHandler,
    RegisterUserCommand,
    RegisterUserHandler,
    RequestPasswordResetCommand,
    RequestPasswordResetHandler,
    ResetPasswordCommand,
    ResetPasswordHandler,
)
from app.presentation import deps
from app.presentation.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterProviderRequest,
    RegisterUserRequest,
    ResetPasswordRequest,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=201)
def register_user(body: RegisterUserRequest, users=Depends(deps.get_user_repo)):
    return RegisterUserHandler(users).handle(
        RegisterUserCommand(name=body.name, email=body.email, password=body.password)
    )


@router.post("/register-provider", status_code=201)
def register_provider(
    body: RegisterProviderRequest,
    users=Depends(deps.get_user_repo),
    providers=Depends(deps.get_provider_repo),
    categories=Depends(deps.get_category_repo),
    geocoder=Depends(deps.get_geocoder),
):
    return RegisterProviderHandler(users, providers, categories, geocoder).handle(
        RegisterProviderCommand(
            name=body.name,
            document=body.document,
            category_ids=body.categoryIds,
            bairro=body.bairro,
            rua=body.rua,
            numero=body.numero,
            whatsapp=body.whatsapp,
            description=body.description,
            email=body.email,
            password=body.password,
        )
    )


@router.post("/login")
def login(
    body: LoginRequest,
    users=Depends(deps.get_user_repo),
    providers=Depends(deps.get_provider_repo),
):
    return LoginHandler(users, providers).handle(LoginCommand(email=body.email, password=body.password))


@router.post("/refresh")
def refresh(
    body: RefreshRequest,
    users=Depends(deps.get_user_repo),
    providers=Depends(deps.get_provider_repo),
):
    return RefreshTokenHandler(users, providers).handle(RefreshTokenCommand(refresh_token=body.refreshToken))


@router.post("/logout", status_code=204)
def logout(body: RefreshRequest, users=Depends(deps.get_user_repo)):
    LogoutHandler(users).handle(LogoutCommand(refresh_token=body.refreshToken))


@router.post("/forgot-password", status_code=202)
def forgot_password(
    body: ForgotPasswordRequest,
    users=Depends(deps.get_user_repo),
    email_service=Depends(deps.get_email_service),
):
    RequestPasswordResetHandler(users, email_service).handle(
        RequestPasswordResetCommand(email=body.email)
    )
    return {"message": "Se o e-mail estiver cadastrado, enviaremos um link de recuperação."}


@router.post("/reset-password", status_code=204)
def reset_password(body: ResetPasswordRequest, users=Depends(deps.get_user_repo)):
    ResetPasswordHandler(users).handle(
        ResetPasswordCommand(token=body.token, new_password=body.newPassword)
    )
