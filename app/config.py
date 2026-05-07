# Env vars (Gemini Key, Tesseract Path)
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SECRET_KEY: str = "dev-only-change-me"
    GEMINI_API_KEY: str = ""
    DATA_DIR: str = "./data"
    DEBUG: bool = True
    TESSERACT_CMD: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def data_path(self) -> Path:
        p = Path(self.DATA_DIR).resolve()
        p.mkdir(parents=True, exist_ok=True)
        (p / "uploads").mkdir(parents=True, exist_ok=True)
        return p

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.data_path / 'app.db'}"

settings = Settings()