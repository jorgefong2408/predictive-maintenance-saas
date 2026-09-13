from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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


def _register_failed_attempt(db: Session, email: str, now: datetime) -> None:
    attempt = db.query(LoginAttempt).filter(LoginAttempt.email == email).first()
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
    db.commit()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_tenant(payload: RegisterTenantRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Crea un tenant nuevo con su primer usuario admin (UC3: aislamiento multi-tenant)."""
    tenant = Tenant(name=payload.tenant_name, slug=payload.tenant_slug)
    db.add(tenant)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El slug de tenant ya existe") from exc

    admin = User(
        tenant_id=tenant.id,
        email=payload.admin_email,
        hashed_password=hash_password(payload.admin_password),
        role="admin",
    )
    db.add(admin)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El email ya está registrado") from exc

    token = create_access_token(user_id=admin.id, tenant_id=tenant.id, role=admin.role)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> TokenResponse:
    now = datetime.now(UTC)
    email = form_data.username

    attempt = db.query(LoginAttempt).filter(LoginAttempt.email == email).first()
    locked_until = _as_aware_utc(attempt.locked_until) if attempt else None
    if locked_until and locked_until > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Probá de nuevo más tarde.",
        )

    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        _register_failed_attempt(db, email, now)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email o contraseña incorrectos")

    if attempt is not None:
        db.delete(attempt)
        db.commit()

    token = create_access_token(user_id=user.id, tenant_id=user.tenant_id, role=user.role)
    return TokenResponse(access_token=token)
