from __future__ import annotations

from pydantic import BaseModel, Field

SIGNAL = (
    "tab_switch|window_blur|fullscreen_exit|page_refresh|copy|paste|right_click|"
    "devtools_open|print_screen|multiple_login|multiple_device|network_disconnect|idle_timeout"
)


class StartProctorIn(BaseModel):
    exam_session_id: str
    candidate_id: str
    drive_id: str | None = None
    fingerprint: str | None = None
    ip: str | None = None
    browser: str | None = None


class EventIn(BaseModel):
    type: str = Field(pattern=f"^({SIGNAL})$")
    ip: str | None = None
    browser: str | None = None
    device: str | None = None
    meta: dict = {}
