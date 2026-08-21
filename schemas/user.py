from pydantic import BaseModel
from typing import Optional

class UpdateUserDto(BaseModel):
    full_name: str
    gender: str
    phone_number: str

class UserResponse(BaseModel):
    id: int
    full_name: str
    gender: str
    phone_number: str
    attendance_count: Optional[int] = 0
