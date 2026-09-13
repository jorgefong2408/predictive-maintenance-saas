from pydantic import BaseModel, EmailStr, Field


class RegisterTenantRequest(BaseModel):
    """Registra un tenant nuevo junto con su primer usuario admin (UC3)."""

    tenant_name: str = Field(min_length=1)
    tenant_slug: str = Field(min_length=1, pattern=r"^[a-z0-9-]+$")
    admin_email: EmailStr
    admin_password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    tenant_id: str
    email: EmailStr
    role: str

    model_config = {"from_attributes": True}
