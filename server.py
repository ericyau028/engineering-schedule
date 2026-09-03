import datetime as dt
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


BASE = Path(__file__).resolve().parent
PUBLIC = BASE / "public"
DATA = BASE / "data"
DATA_FILE = DATA / "schedule.json"

TZ = dt.timezone(dt.timedelta(hours=8))
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def now_iso():
    return dt.datetime.now(TZ).isoformat(timespec="seconds")


def local_dt(date_str, time_str):
    d = dt.date.fromisoformat(date_str)
    h, m = (int(x) for x in time_str.split(":"))
    return dt.datetime(d.year, d.month, d.day, h, m, tzinfo=TZ)


def make_item(letter, date_str, time_str, content, owner, item, stage,
              description, end_time, end_date, relation, source):
    end_datetime = None
    if end_time and end_date:
        end_datetime = local_dt(end_date, end_time).isoformat()
    return {
        "id": f"{source}-{letter}",
        "letter": letter,
        "date": date_str,
        "time": time_str,
        "datetime": local_dt(date_str, time_str).isoformat(),
        "content": content or "",
        "owner": owner or "",
        "item": item or "",
        "stage": stage or "",
        "description": description or "",
        "end_time": end_time,
        "end_date": end_date,
        "end_datetime": end_datetime,
        "relation": relation,
        "source": source,
    }


def next_letter(used):
    used = set(used)
    i = 0
    while True:
        if i < 26:
            candidate = chr(ord("a") + i)
        else:
            candidate = "a" + chr(ord("a") + (i - 26))
        if candidate not in used:
            return candidate
        i += 1


def validate_payload(payload):
    date_str = str(payload.get("date") or "").strip()
    time_str = str(payload.get("time") or "").strip()
    end_time = str(payload.get("end_time") or "").strip()
    content = str(payload.get("content") or "").strip()
    owner = str(payload.get("owner") or "").strip()
    item = str(payload.get("item") or "").strip()
    description = str(payload.get("description") or "").strip()

    if not DATE_RE.match(date_str):
        return "日期格式必須是 YYYY-MM-DD", None
    if not TIME_RE.match(time_str):
        return "開始時間格式必須是 HH:MM", None
    if end_time and not TIME_RE.match(end_time):
        return "結束時間格式必須是 HH:MM", None
    if end_time and end_time == time_str:
        return "結束時間不能與開始時間相同", None
    if not content:
        return "請輸入內容", None
    if not owner:
        return "請輸入負責人", None
    if not item:
        return "請輸入項目分鐘", None
    try:
        start_date = dt.date.fromisoformat(date_str)
    except ValueError:
        return "日期格式不正確", None

    return None, {
        "date": date_str,
        "time": time_str,
        "end_time": end_time or None,
        "content": content,
        "owner": owner,
        "item": item,
        "description": description,
        "start_date": start_date,
    }


def save_items(items):
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DATA_FILE)


def load_items():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    save_items([])
    return []


class Handler(BaseHTTPRequestHandler):
    server_version = "EngineeringSchedule/1.0"

    def log_message(self, fmt, *args):
        print(f"[server] {fmt % args}")

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

    def _serve_static(self, path):
        if path == "/":
            path = "/index.html"
        relative = unquote(path).lstrip("/")
        target = (PUBLIC / relative).resolve()
        if not str(target).startswith(str(PUBLIC.resolve())):
            self.send_error(403)
            return
        if not target.is_file():
            self.send_error(404)
            return
        mime = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".ico": "image/x-icon",
        }.get(target.suffix.lower(), "application/octet-stream")
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/schedule":
            self._send_json({"items": load_items(), "now": now_iso()})
            return
        if parsed.path == "/api/now":
            self._send_json({"now": now_iso()})
            return
        self._serve_static(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/schedule":
            self._send_json({"error": "not found"}, 404)
            return

        payload = self._read_json()
        if not isinstance(payload, dict):
            self._send_json({"error": "invalid JSON body"}, 400)
            return

        err, vals = validate_payload(payload)
        if err:
            self._send_json({"error": err}, 400)
            return
        if not vals["end_time"]:
            self._send_json({"error": "結束時間格式必須是 HH:MM"}, 400)
            return

        end_date = (vals["start_date"] + dt.timedelta(days=1)).isoformat() \
            if vals["end_time"] <= vals["time"] else vals["start_date"].isoformat()

        items = load_items()
        used = [item["letter"] for item in items]
        start_letter = next_letter(used)
        used.append(start_letter)
        end_letter = next_letter(used)

        start_item = make_item(
            start_letter, vals["date"], vals["time"], vals["content"],
            vals["owner"], vals["item"], "開始", vals["description"],
            vals["end_time"], end_date, end_letter, "form",
        )
        end_item = make_item(
            end_letter, end_date, vals["end_time"], vals["content"],
            vals["owner"], vals["item"], "結束", vals["description"],
            None, None, None, "form",
        )
        items.extend([start_item, end_item])
        items.sort(key=lambda i: i["datetime"])
        save_items(items)
        self._send_json({"items": [start_item, end_item]}, 201)

    def do_PUT(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/schedule":
            self._send_json({"error": "not found"}, 404)
            return
        query = parse_qs(parsed.query)
        item_id = (query.get("id") or [None])[0]
        if not item_id:
            self._send_json({"error": "missing id"}, 400)
            return

        payload = self._read_json()
        if not isinstance(payload, dict):
            self._send_json({"error": "invalid JSON body"}, 400)
            return

        err, vals = validate_payload(payload)
        if err:
            self._send_json({"error": err}, 400)
            return

        items = load_items()
        item = next((x for x in items if x["id"] == item_id), None)
        if not item:
            self._send_json({"error": "item not found"}, 404)
            return

        pair_start = bool(item.get("end_time"))
        if pair_start and not vals["end_time"]:
            self._send_json({"error": "結束時間格式必須是 HH:MM"}, 400)
            return

        new_relation = str(payload.get("relation") or "").strip() or None
        if new_relation == item["letter"]:
            self._send_json({"error": "關聯不能指向自己"}, 400)
            return
        if new_relation and not any(
            x["letter"] == new_relation and x["id"] != item["id"] for x in items
        ):
            self._send_json({"error": "找不到關聯的字母"}, 400)
            return

        relation_changed = new_relation != item.get("relation")
        target = next(
            (x for x in items if x["letter"] == new_relation),
            None,
        ) if new_relation else None

        end_time = vals["end_time"] if pair_start else item.get("end_time")
        end_date = None
        if end_time:
            end_date = (vals["start_date"] + dt.timedelta(days=1)).isoformat() \
                if end_time <= vals["time"] else vals["start_date"].isoformat()

        item.update({
            "date": vals["date"],
            "time": vals["time"],
            "datetime": local_dt(vals["date"], vals["time"]).isoformat(),
            "content": vals["content"],
            "owner": vals["owner"],
            "item": vals["item"],
            "description": vals["description"],
            "end_time": end_time,
            "end_date": end_date,
            "end_datetime": local_dt(end_date, end_time).isoformat()
                if end_time and end_date else None,
            "relation": new_relation,
        })

        if target and end_time and not relation_changed:
            target.update({
                "date": end_date,
                "time": end_time,
                "datetime": local_dt(end_date, end_time).isoformat(),
                "content": vals["content"],
                "owner": vals["owner"],
                "item": vals["item"],
                "description": vals["description"],
            })

        items.sort(key=lambda i: i["datetime"])
        save_items(items)
        self._send_json({"items": [item] + ([target] if target else [])})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/schedule":
            self._send_json({"error": "not found"}, 404)
            return
        query = parse_qs(parsed.query)
        items = load_items()

        if query.get("all") and query["all"][0] in ("1", "true"):
            save_items([])
            self._send_json({"ok": True, "deleted": len(items)})
            return

        before = (query.get("before") or [None])[0]
        if before:
            if not DATE_RE.match(before):
                self._send_json({"error": "日期格式必須是 YYYY-MM-DD"}, 400)
                return
            remaining = [item for item in items if item["date"] > before]
            save_items(remaining)
            self._send_json({"ok": True, "deleted": len(items) - len(remaining)})
            return

        item_id = (query.get("id") or [None])[0]
        if not item_id:
            self._send_json({"error": "missing id"}, 400)
            return
        remaining = [item for item in items if item["id"] != item_id]
        if len(remaining) == len(items):
            self._send_json({"error": "item not found"}, 404)
            return
        save_items(remaining)
        self._send_json({"ok": True})


def main():
    port = int(os.environ.get("PORT", "8780"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"工程排程表已啟動: http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
