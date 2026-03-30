from __future__ import annotations

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    ok: bool
    message: str = ""


class VerifyTokenRequest(BaseModel):
    token: str = ""
    use_stored: bool = False


class SetTokenRequest(BaseModel):
    token: str = Field(min_length=1)


class ConfigUpdateRequest(BaseModel):
    github_token: str | None = None
    gist_id: str | None = None
    gist_filename: str | None = None
    tencent_map_key: str | None = None
    tls_insecure: bool | None = None
    whitelist_category_ids: list[int] | None = None
    whitelist_grade: list[str] | None = None
    whitelist_academy: list[str] | None = None


class SignActionRequest(BaseModel):
    address: str = ""
    latitude: float
    longitude: float
