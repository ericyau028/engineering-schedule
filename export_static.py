import json
from pathlib import Path


BASE = Path(__file__).resolve().parent
DATA_FILE = BASE / "data" / "schedule.json"
OUT_FILE = BASE / "public" / "schedule-static.json"


def main():
    if DATA_FILE.exists():
        items = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    else:
        items = []
    OUT_FILE.write_text(
        json.dumps({"items": items}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已寫入 {len(items)} 列: {OUT_FILE}")


if __name__ == "__main__":
    main()
