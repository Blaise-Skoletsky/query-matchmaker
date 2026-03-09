from pydantic import BaseModel


class SimilarQueryResponse(BaseModel):
    id: str
    raw_text: str
    intent: str | None
    category: str | None
    similarity: float


class TrendingCategoryResponse(BaseModel):
    category: str
    intent: str | None
    count: int


class DemandGapResponse(BaseModel):
    category: str
    needed_intent: str
    demand_count: int
    supply_count: int
    gap: int
