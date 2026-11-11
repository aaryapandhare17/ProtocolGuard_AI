from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    protocolguard_env: str = "development"
    require_postgres: bool = False
    serve_frontends: bool = True
    static_directory: str | None = None
    database_url: str = "sqlite:///./protocolguard.db"
    cors_origins: str = "http://localhost:5173,http://localhost:5174"

    ip_auto_restrict_enabled: bool = True
    ip_abuse_threshold: int = Field(default=30,ge=5,le=1000)
    ip_abuse_window_seconds: int = Field(default=60,ge=10,le=3600)
    ip_restriction_seconds: int = Field(default=120,ge=5,le=86400)
    auto_block_enabled: bool = True
    block_threshold: float = Field(default=60, ge=0, le=100, allow_inf_nan=False)
    simulation_enabled: bool = True
    ml_comparison_report: str = "ml/evaluation/comparison-v1.json"
    ml_enabled: bool = True
    ml_model_directory: str = "ml/artifacts/bank-v1"
    risk_fsm_weight: float = Field(default=0.30, ge=0, le=1, allow_inf_nan=False)
    risk_rf_weight: float = Field(default=0.35, ge=0, le=1, allow_inf_nan=False)
    risk_if_weight: float = Field(default=0.10, ge=0, le=1, allow_inf_nan=False)
    risk_behavior_weight: float = Field(default=0.25, ge=0, le=1, allow_inf_nan=False)
    risk_window_seconds: int = Field(default=60, ge=10, le=3600)
    risk_half_life_seconds: int = Field(default=600, ge=1, le=86400)
    risk_max_events: int = Field(default=200, ge=10, le=1000)

    @model_validator(mode="after")
    def validate_risk_weights(self):
        total = self.risk_fsm_weight + self.risk_rf_weight + self.risk_if_weight + self.risk_behavior_weight
        if abs(total - 1) > 1e-9:
            raise ValueError("Risk weights must sum to one")
        return self


settings = Settings()
