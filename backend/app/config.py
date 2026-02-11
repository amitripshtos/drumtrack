from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    storage_dir: Path = Path("./storage")
    frontend_url: str = "http://localhost:3000"

    model_config = {"env_file": "../.env", "env_file_encoding": "utf-8"}

    @property
    def jobs_dir(self) -> Path:
        return self.storage_dir / "jobs"


settings = Settings()
