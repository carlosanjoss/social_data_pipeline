from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # MongoDB
    mongo_uri: str = "mongodb://admin:change_me@localhost:27017/radar_odio?authSource=admin"
    mongo_db: str = "radar_odio"

    # PostgreSQL
    postgres_uri: str = "postgresql://radar:change_me@localhost:5432/radar_odio"

    # Redis
    redis_uri: str = "redis://localhost:6379/0"

    # Caminhos dos scrapers
    reddit_data_path: Path = Path("../../scrappers/reddit_scrapperv2academic/src/reddit_pipeline/data")
    # PostgreSQL próprio do projeto irmão ../reddit_pipeline. Quando a URI não
    # é informada, o conector lê DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD
    # do arquivo abaixo.
    reddit_pipeline_enabled: bool = True
    reddit_pipeline_uri: str | None = None
    reddit_pipeline_env_path: Path = Path("../reddit_pipeline/.env")
    twitter_data_path: Path = Path("../../scrappers/twitter_scrapper_project/data/json")
    youtube_data_path: Path = Path("../../scrappers/youtube_scrapper/data")
    facebook_data_path: Path = Path("../../scrappers/facebook_scrapper/data/output")
    instagram_data_path: Path = Path("../../scrappers/instagram_scrapper/data")
    tiktok_data_path: Path = Path("../../scrappers/tiktok_scrapper/data")
    farol_exports_path: Path = Path("../farol_digital_json_api/exports")

    # Pipeline
    batch_size: int = 100
    log_level: str = "INFO"
    target_language: str = "pt-BR"


settings = Settings()
