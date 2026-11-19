from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import (
    SignupRequest,
    SignupResponse,
    LoginRequest,
    TokenResponse,
    VerifyEmailRequest,
    RefreshTokenRequest,
    AcceptInviteRequest,
    SwitchOrgRequest,
)
from app.auth.service import AuthService
from app.config import get_settings
from app.db.models.user import User
from app.dependencies import get_db, get_current_user

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=SignupResponse, status_code=201)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    user, org, raw_token = await service.signup(body)
    
    return SignupResponse(
        user_id=user.id,
        email=user.email,
        organization_id=org.id,
        organization_name=org.name,
        message="Account created successfully. Please verify your email.",
        email_verification_token=raw_token if settings.ENVIRONMENT in ("development", "test") else None,
    )


@router.post("/verify-email")
async def verify_email(body: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    user = await service.verify_email(body.token)
    return {"status": "ok", "message": "Email verified successfully", "email": user.email}


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    access_token, refresh_token, user, org, role = await service.login(body)

    # Set httpOnly cookie for secure refresh
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=settings.ENVIRONMENT != "development",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        organization_id=org.id if org else None,
        role=role,
    )


@router.post("/refresh", response_model=dict)
async def refresh_token(
    body: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    new_access_token = await service.refresh_access_token(body.refresh_token)
    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/accept-invite")
async def accept_invite(body: AcceptInviteRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    user, membership = await service.accept_invitation(body)
    return {
        "status": "ok",
        "message": "Invitation accepted successfully",
        "user_id": user.id,
        "organization_id": membership.org_id,
        "role": membership.org_role,
    }


@router.post("/switch-org", response_model=TokenResponse)
async def switch_org(
    body: SwitchOrgRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    access_token, refresh_token, org, role = await service.switch_organization(user, body.org_id)

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=settings.ENVIRONMENT != "development",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        organization_id=org.id,
        role=role,
    )
