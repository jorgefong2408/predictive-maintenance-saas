from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.login_attempt import LoginAttempt
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import RegisterTenantRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# Rate limiting de login (bug de seguridad real: no había ninguno). No es
# perfectamente atómico bajo concurrencia extrema (read-then-write, no un
# UPSERT con incremento atómico) — para el modelo de amenaza de este
# proyecto, tener *algún* límite persistente entre réplicas ya es la mejora
# real; afinar la última carrera de concurrencia no lo es.
MAX_FAILED_ATTEMPTS = 5
ATTEMPT_WINDOW_MINUTES = 15
LOCKOUT_MINUTES = 15


def _as_aware_utc(dt: datetime | None) -> datetime | None:
    """Postgres preserva tzinfo en columnas DateTime(timezone=True); SQLite
    (donde corren los tests) no, sin importar cómo se declare la columna —
    siempre devuelve naive en el round-trip. Se asume UTC (todo lo que
    escribe este módulo ya lo es) para poder comparar sin que explote con
    'can't subtract offset-naive and offset-aware datetimes'."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


async def _register_failed_attempt(db: AsyncSession, email: str, now: datetime) -> None:
    attempt = (
        await db.execute(select(LoginAttempt).where(LoginAttempt.email == email))
    ).scalar_one_or_none()
    if attempt is None:
        attempt = LoginAttempt(email=email, failed_count=0, window_started_at=now)
        db.add(attempt)

    window_started_at = _as_aware_utc(attempt.window_started_at)
    window_expired = window_started_at is None or (now - window_started_at) > timedelta(
        minutes=ATTEMPT_WINDOW_MINUTES
    )
    if window_expired:
        attempt.window_started_at = now
        attempt.failed_count = 0

    attempt.failed_count += 1
    if attempt.failed_count >= MAX_FAILED_ATTEMPTS:
        attempt.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
    await db.commit()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_tenant(payload: RegisterTenantRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Crea un tenant nuevo con su primer usuario admin (UC3: aislamiento multi-tenant)."""
    tenant = Tenant(name=payload.tenant_name, slug=payload.tenant_slug)
    db.add(tenant)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El slug de tenant ya existe") from exc

    # bcrypt es CPU-bound y bloqueante (~100-200ms por el work factor) --
    # correrlo directo en la ruta async congelaría el event loop para TODAS
    # las requests en curso, no solo esta. run_in_threadpool lo saca del loop.
    hashed_password = await run_in_threadpool(hash_password, payload.admin_password)
    admin = User(
        tenant_id=tenant.id,
        email=payload.admin_email,
        hashed_password=hashed_password,
        role="admin",
    )
    db.add(admin)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El email ya está registrado") from exc

    token = create_access_token(user_id=admin.id, tenant_id=tenant.id, role=admin.role)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)) -> TokenResponse:
    now = datetime.now(UTC)
    email = form_data.username

    attempt = (
        await db.execute(select(LoginAttempt).where(LoginAttempt.email == email))
    ).scalar_one_or_none()
    locked_until = _as_aware_utc(attempt.locked_until) if attempt else None
    if locked_until and locked_until > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Probá de nuevo más tarde.",
        )

    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not await run_in_threadpool(verify_password, form_data.password, user.hashed_password):
        await _register_failed_attempt(db, email, now)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email o contraseña incorrectos")

    if attempt is not None:
        await db.delete(attempt)
        await db.commit()

    token = create_access_token(user_id=user.id, tenant_id=user.tenant_id, role=user.role)
    return TokenResponse(access_token=token)
