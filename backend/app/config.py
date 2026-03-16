from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://matchmaker:matchmaker@localhost:5432/matchmaker"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"
    embedding_model: str = "all-MiniLM-L6-v2"
    redis_url: str = "redis://localhost:6379"
    match_score_threshold: float = 0.7
    candidate_limit: int = 50
    llm_eval_limit: int = 10

    model_config = {"env_file": ".env"}


settings = Settings()
