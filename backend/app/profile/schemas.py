from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ContactInfo(BaseModel):
    phone: str = ""
    email: str = ""
    address: str = ""
    site: str = ""


class ProfileIn(BaseModel):
    org_name: str = Field(default="", max_length=500)
    inn: str = Field(default="", max_length=20)
    contacts: ContactInfo = Field(default_factory=ContactInfo)
    bank_requisites: str = ""
    utp: list[str] = Field(default_factory=list)
    cases: list[str] = Field(default_factory=list)
    guarantee: str = ""
    logo_url: str = Field(default="", max_length=1000)


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_name: str
    inn: str
    contacts: dict
    bank_requisites: str
    utp: list[str]
    cases: list[str]
    guarantee: str
    logo_url: str
    updated_at: datetime
