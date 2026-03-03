from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://stock_user:stock_pass@localhost:5432/stock_hub"
    pdf_storage_path: str = "./storage/pdfs"
    scheduler_enabled: bool = False
    scheduler_cron_hour: int = 7
    log_level: str = "INFO"
    admin_api_key: str = ""
    # Alert settings
    alert_email_to: str = ""
    alert_smtp_host: str = "localhost"
    alert_smtp_port: int = 587
    alert_smtp_user: str = ""
    alert_smtp_pass: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
