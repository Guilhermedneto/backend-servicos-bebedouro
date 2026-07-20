from typing import Literal

from pydantic import BaseModel, EmailStr, Field

PlanLiteral = Literal["free", "essential", "premium"]
BillingCycleLiteral = Literal["monthly", "annual"]


class RegisterUserRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RegisterProviderRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    document: str = Field(min_length=11, max_length=18)
    categoryIds: list[str] = Field(min_length=1, max_length=4)
    bairro: str = Field(min_length=1, max_length=100)
    rua: str = Field(min_length=1, max_length=150)
    numero: str = Field(min_length=1, max_length=20)
    whatsapp: str = Field(min_length=10, max_length=20)
    description: str = Field(min_length=1, max_length=1000)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    plan: PlanLiteral = "free"
    billingCycle: BillingCycleLiteral | None = None


class ChangePlanRequest(BaseModel):
    plan: PlanLiteral
    billingCycle: BillingCycleLiteral | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refreshToken: str = Field(min_length=1)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    newPassword: str = Field(min_length=8, max_length=128)


class UpdateProviderRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    categoryIds: list[str] = Field(min_length=1, max_length=4)
    bairro: str = Field(min_length=1, max_length=100)
    rua: str = Field(min_length=1, max_length=150)
    numero: str = Field(min_length=1, max_length=20)
    whatsapp: str = Field(min_length=10, max_length=20)
    description: str = Field(min_length=1, max_length=1000)


class ReviewRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=1, max_length=500)


class AiSearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=300)


class CategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class CategoryUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    active: bool
