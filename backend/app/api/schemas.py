from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    citations: list[dict]
    guardrail_warnings: list[str]
    activity_log: list[dict]
    tool_calls: list[dict]
