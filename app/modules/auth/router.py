from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import AuthServiceDep, CurrentUser
from app.core.email import send_password_reset_email, send_verification_email
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    Message,
    RefreshRequest,
    ResetPasswordRequest,
    TokenPair,
    VerifyEmailRequest,
)
from app.modules.users.schemas import UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, service: AuthServiceDep, background: BackgroundTasks):
    user, token = await service.register(data)
    background.add_task(send_verification_email, user.email, token)
    return user


@router.post("/login", response_model=TokenPair)
async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], service: AuthServiceDep):
    # OAuth2 form: `username` carries the email. This also makes Swagger's "Authorize" button work.
    return await service.login(form.username, form.password)


@router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshRequest, service: AuthServiceDep):
    return await service.refresh(data.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: RefreshRequest, service: AuthServiceDep) -> Response:
    await service.logout(data.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(current_user: CurrentUser, service: AuthServiceDep) -> Response:
    await service.logout_all(current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/change-password", response_model=Message)
async def change_password(
    data: ChangePasswordRequest, current_user: CurrentUser, service: AuthServiceDep
):
    await service.change_password(current_user, data.current_password, data.new_password)
    return Message(detail="Password changed. Please log in again.")


@router.post("/forgot-password", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    data: ForgotPasswordRequest, service: AuthServiceDep, background: BackgroundTasks
):
    token = await service.request_password_reset(data.email)
    if token:
        background.add_task(send_password_reset_email, data.email.lower(), token)
    # Same answer whether or not the email exists -> no user enumeration.
    return Message(detail="If that email is registered, a reset link has been sent.")


@router.post("/reset-password", response_model=Message)
async def reset_password(data: ResetPasswordRequest, service: AuthServiceDep):
    await service.reset_password(data.token, data.new_password)
    return Message(detail="Password updated. You can now log in.")


@router.post("/verify-email", response_model=Message)
async def verify_email(data: VerifyEmailRequest, service: AuthServiceDep):
    await service.verify_email(data.token)
    return Message(detail="Email verified.")


@router.post(
    "/resend-verification", response_model=Message, status_code=status.HTTP_202_ACCEPTED
)
async def resend_verification(
    current_user: CurrentUser, service: AuthServiceDep, background: BackgroundTasks
):
    token = service.create_verification_token_for(current_user)
    background.add_task(send_verification_email, current_user.email, token)
    return Message(detail="Verification email sent.")
