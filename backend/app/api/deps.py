from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import InvalidTokenError, decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class Claims:
    def __init__(self, user_id: str, tenant_id: str, role: str):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role = role


def get_current_claims(token: str = Depends(oauth2_scheme)) -> Claims:
    try:
        payload = decode_access_token(token)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas o expiradas",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return Claims(user_id=payload["sub"], tenant_id=payload["tenant_id"], role=payload["role"])


def require_role(*allowed_roles: str):
    def _check(claims: Claims = Depends(get_current_claims)) -> Claims:
        if claims.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rol insuficiente")
        return claims

    return _check


async def get_tenant_scoped_db(
    claims: Claims = Depends(get_current_claims),
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[AsyncSession, None]:
    """Defensa en profundidad (ver migración `83dc2610fe35`): además del
    `.filter(tenant_id=...)` que ya pone cada endpoint, fija el tenant actual
    como variable de sesión de Postgres para que las políticas de Row-Level
    Security lo hagan cumplir también a nivel de base — un query que olvide
    el filtro sigue sin poder ver filas de otro tenant.

    Bug real encontrado probando esto contra Postgres de verdad: con
    `set_config(..., true)` ("is_local", equivalente a SET LOCAL) el valor se
    descarta en el PRIMER commit — pero varias rutas hacen más de un commit
    por request (insertar la predicción, después insertar la alerta), y el
    segundo `db.refresh(...)` fallaba con "invalid input syntax for type
    uuid: ''" porque el contexto ya se había perdido. Se usa `false`
    ("session", sobrevive a los commits del connection mientras dura) y se
    resetea explícitamente al terminar el request (`finally`) — así una
    conexión que vuelve al pool nunca arrastra el tenant de un request
    anterior al siguiente.

    En SQLite (dev local sin Docker) no hace nada — RLS no existe ahí, el
    filtro de aplicación sigue siendo la única defensa, como siempre fue.
    """
    is_postgres = db.bind.dialect.name == "postgresql"
    if is_postgres:
        await db.execute(text("SELECT set_config('app.current_tenant_id', :tid, false)"), {"tid": claims.tenant_id})
    try:
        yield db
    finally:
        if is_postgres:
            await db.execute(text("SELECT set_config('app.current_tenant_id', '', false)"))
            await db.commit()
