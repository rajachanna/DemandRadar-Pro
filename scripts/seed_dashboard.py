"""ONLY for an explicitly synthetic local preview; never production lead data."""
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from demandradar.config import Settings
from demandradar.storage import Store
from scripts.demo import records


def main():
    settings = Settings.from_env()
    if not settings.demo_mode or "--yes-synthetic" not in sys.argv:
        raise SystemExit("Refusing to insert sample leads unless DR_DEMO_MODE=true and --yes-synthetic is set")
    store = Store(settings.db_path)
    result = store.ingest(records())
    print("SYNTHETIC DEMO ONLY:",result)


if __name__ == "__main__":
    main()
