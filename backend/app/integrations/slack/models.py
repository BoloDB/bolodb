from pydantic import BaseModel
from datetime import datetime


class SlackInstallationResponse(BaseModel):
    id: str
    team_id: str
    team_name: str
    bot_user_id: str
    scopes: str | None
    created_at: datetime
