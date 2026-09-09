from typing import Optional

from pydantic import BaseModel, Field


class UpdateUserDto(BaseModel):
    """Partial update payload.

    Every field is optional so the dashboard's edit form can send only what it
    actually shows. When these were required, the form had to invent a value for
    gender on every save.
    """

    full_name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    gender: Optional[str] = None
    phone_number: Optional[str] = Field(default=None, max_length=30)


class UserResponse(BaseModel):
    id: int
    full_name: str
    gender: Optional[str] = None
    phone_number: Optional[str] = None
    attendance_count: int = 0
