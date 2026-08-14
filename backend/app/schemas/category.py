import datetime
from typing import Optional

from pydantic import BaseModel


class AIClassifyRequest(BaseModel):
    user_input: str


class AIClassifyResponse(BaseModel):
    category: str


class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(CategoryBase):
    pass


class CategoryInfo(CategoryBase):
    id: int
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None

    class Config:
        orm_mode = True
