"""Environment-only configuration. Never ship API keys in static files."""
from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    db_path: str = "./data/demandradar.sqlite"
    operator_key: str = ""
    github_token: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    telegram_token: str = ""
    telegram_chat_id: str = ""
    demo_mode: bool = False
    max_scan_items: int = 20

    @classmethod
    def from_env(cls) -> "Settings":
        def bounded_int(value: str, default: int) -> int:
            try:
                return max(1, min(30, int(value)))
            except ValueError:
                return default

        return cls(
            db_path=os.getenv("DR_DB_PATH", "./data/demandradar.sqlite"),
            operator_key=os.getenv("DR_OPERATOR_KEY", ""),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            telegram_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            demo_mode=os.getenv("DR_DEMO_MODE", "false").lower() in ("1", "true", "yes"),
            max_scan_items=bounded_int(os.getenv("DR_MAX_SCAN_ITEMS", "20"), 20),
        )

    @property
    def operator_enabled(self) -> bool:
        return len(self.operator_key.encode("utf-8")) >= 24

    def ensure_dirs(self) -> None:
        Path(self.db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
