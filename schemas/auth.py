from pydantic import BaseModel


class LoginDto(BaseModel):
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
