# Pydantic schemas for authentication request/response bodies.

from pydantic import BaseModel, EmailStr, field_validator

MIN_PASSWORD_LENGTH = 12

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None

    @field_validator("password")
    @classmethod
    def password_must_be_strong_enough(cls, value):
        if len(value) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
        return value

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str | None = None

class GoogleAuthRequest(BaseModel):
    credential: str
