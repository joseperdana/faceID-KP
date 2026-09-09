from pydantic import BaseModel, Field


class UpdateUserDto(BaseModel):
    """Partial update payload.

    Every field is optional so the dashboard's edit form can send only what it
    actually shows. When these were required, the form had to invent a value for
    gender on every save.
    """

    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    gender: str | None = None
    phone_number: str | None = Field(default=None, max_length=30)


class UserResponse(BaseModel):
    id: int
    full_name: str
    gender: str | None = None
    phone_number: str | None = None
    attendance_count: int = 0
