from pydantic import BaseModel, ConfigDict, EmailStr, Field


class OrgIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class OrgOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    user_count: int = 0


class InviteIn(BaseModel):
    email: EmailStr
    role: str = "estimator"


class UpdateUserIn(BaseModel):
    role: str | None = None
    status: str | None = None
