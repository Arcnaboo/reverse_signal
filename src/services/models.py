from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict

@dataclass
class TeamModel:
    id: int
    name: str
    short_name: Optional[str] = None
    tla: Optional[str] = None          # Three-letter acronym
    crest_url: Optional[str] = None
    venue: Optional[str] = None
    founded: Optional[int] = None
    last_updated: Optional[datetime] = None


@dataclass
class CompetitionModel:
    code: str
    name: str
    area: Optional[str] = None
    season_start: Optional[datetime] = None
    season_end: Optional[datetime] = None


@dataclass
class MatchScore:
    home: Optional[int] = None
    away: Optional[int] = None


@dataclass
class MatchModel:
    id: int
    utc_date: datetime
    status: str
    competition: str
    home_team: TeamModel
    away_team: TeamModel
    score: MatchScore
    stage: Optional[str] = None
    group: Optional[str] = None
    last_updated: Optional[datetime] = None
