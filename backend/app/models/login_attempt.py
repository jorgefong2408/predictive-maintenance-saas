from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LoginAttempt(Base):
    """Rate limiting de /auth/login, persistido en Postgres (no en memoria)
    para que sea correcto entre réplicas — un atacante no puede resetear su
    contador simplemente pegándole a otro pod. Por email, no por tenant: en
    el momento del intento fallido no sabemos a qué tenant pertenece (o si
    el email ni siquiera existe) — mismo motivo por el que `users` tampoco
    lleva Row-Level Security.

    `DateTime(timezone=True)` explícito: el resto del código guarda datetimes
    tz-aware (`datetime.now(UTC)`) en columnas SIN este flag, que en el
    round-trip a la base vuelven naive — nunca importó porque nada más las
    comparaba después de recargarlas. Acá sí se comparan (¿venció la ventana
    de intentos?), así que sin esto `now - attempt.window_started_at`
    explota con "can't subtract offset-naive and offset-aware datetimes" en
    el segundo intento fallido (el primero nunca toca la base antes de
    compararse)."""

    __tablename__ = "login_attempts"

    email: Mapped[str] = mapped_column(String, primary_key=True)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
