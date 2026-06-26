from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


class StoreCreate(BaseModel):
    name: str
    address: Optional[str] = None
    industryType: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 1 or len(v) > 200:
            raise ValueError("店铺名称 1-200 字")
        return v


class StoreUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    industryType: Optional[str] = None


class StoreOut(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    industryType: Optional[str] = None
    logoUrl: Optional[str] = None
    createdAt: datetime

    model_config = {"from_attributes": True}
