from __future__ import annotations

import base64
import copy
import importlib.util
import json
import os
import uuid
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
ICONS_DIR = ROOT / "icons"
HISTORY_FILE = DATA_DIR / "history.json"

WAREHOUSE_SEED_FILES = {
    "cafe": DATA_DIR / "warehouse-cafe.py",
    "bar": DATA_DIR / "warehouse-bar.py",
}
CELLAR_FILES = {
    "cafe": DATA_DIR / "cellar-cafe.json",
    "bar": DATA_DIR / "cellar-bar.json",
}
WAREHOUSE_FILES = {
    "cafe": DATA_DIR / "warehouse-cafe.json",
    "bar": DATA_DIR / "warehouse-bar.json",
}

VALID_SHOPS = {"cafe", "bar"}
VALID_LOCATIONS = {"warehouse", "cellar"}

GITHUB_OWNER = os.environ.get("BARMGR_GITHUB_OWNER", "yrotsoukali")
GITHUB_REPO = os.environ.get("BARMGR_GITHUB_REPO", "BarMGR")
GITHUB_BRANCH = os.environ.get("BARMGR_GITHUB_BRANCH", "main")
GITHUB_TOKEN = os.environ.get("BARMGR_GITHUB_TOKEN", "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").strip()
ALLOWED_ORIGIN = os.environ.get("BARMGR_ALLOWED_ORIGIN", "*").strip() or "*"

GITHUB_INVENTORY_FILES = {
    ("cafe", "warehouse"): "data/warehouse-cafe.json",
    ("cafe", "cellar"): "data/cellar-cafe.json",
    ("bar", "warehouse"): "data/warehouse-bar.json",
    ("bar", "cellar"): "data/cellar-bar.json",
}
GITHUB_HISTORY_FILE = "data/history.json"


def load_python_seed(file_path: Path, attribute: str) -> Dict[str, List[Dict[str, Any]]]:
    module_name = f"seed_{file_path.stem.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load seed file: {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    seed = getattr(module, attribute, None)
    if seed is None:
        raise AttributeError(f"Seed attribute {attribute} not found in {file_path}")
    return seed


def build_empty_copy(source: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    return {
        category: [
            {"name": item["name"], "quantity": 0}
            for item in items
        ]
        for category, items in source.items()
    }


def ensure_directory() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def read_json(file_path: Path, default: Any) -> Any:
    if not file_path.exists():
        return copy.deepcopy(default)
    with file_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(file_path: Path, payload: Any) -> None:
    with file_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def github_enabled() -> bool:
    return bool(GITHUB_TOKEN)


def github_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "BarMGR/1.0",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def github_contents_url(repo_path: str) -> str:
    return f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{quote(repo_path)}?ref={quote(GITHUB_BRANCH)}"


def github_request_json(method: str, url: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    body = None
    headers = github_headers()
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {"message": raw or str(exc)}
        raise RuntimeError(data.get("message", str(exc))) from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub connection failed: {exc.reason}") from exc


def github_load_json(repo_path: str, default: Any) -> tuple[Any, str | None]:
    data = github_request_json("GET", github_contents_url(repo_path))
    content = data.get("content")
    if not content:
        return copy.deepcopy(default), data.get("sha")
    decoded = base64.b64decode(content.replace("\n", ""))
    return json.loads(decoded.decode("utf-8")), data.get("sha")


def github_save_json(repo_path: str, payload: Any, message: str, sha: str | None = None) -> str:
    encoded = base64.b64encode(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")).decode("ascii")
    request_payload: Dict[str, Any] = {
        "message": message,
        "content": encoded,
        "branch": GITHUB_BRANCH,
    }
    if sha:
        request_payload["sha"] = sha
    data = github_request_json("PUT", github_contents_url(repo_path), request_payload)
    content = data.get("content") or {}
    return content.get("sha", "")


def ensure_data_files() -> None:
    ensure_directory()

    for shop, seed_path in WAREHOUSE_SEED_FILES.items():
        seed = load_python_seed(seed_path, f"WAREHOUSE_{shop.upper()}")

        warehouse_file = WAREHOUSE_FILES[shop]
        cellar_file = CELLAR_FILES[shop]

        if not warehouse_file.exists():
            write_json(warehouse_file, seed)

        if not cellar_file.exists():
            write_json(cellar_file, build_empty_copy(seed))

    if not HISTORY_FILE.exists():
        write_json(HISTORY_FILE, [])


def normalize_shop(shop: str) -> str:
    shop = shop.lower().strip()
    if shop not in VALID_SHOPS:
        raise ValueError("Invalid shop")
    return shop


def normalize_location(location: str) -> str:
    location = location.lower().strip()
    if location not in VALID_LOCATIONS:
        raise ValueError("Invalid location")
    return location


def inventory_file(shop: str, location: str) -> Path:
    shop = normalize_shop(shop)
    location = normalize_location(location)
    return WAREHOUSE_FILES[shop] if location == "warehouse" else CELLAR_FILES[shop]


def inventory_repo_path(shop: str, location: str) -> str:
    shop = normalize_shop(shop)
    location = normalize_location(location)
    return GITHUB_INVENTORY_FILES[(shop, location)]


def load_inventory(shop: str, location: str) -> Dict[str, List[Dict[str, Any]]]:
    if github_enabled():
        try:
            data, _sha = github_load_json(inventory_repo_path(shop, location), {})
            return data
        except RuntimeError:
            pass
    return read_json(inventory_file(shop, location), {})


def save_inventory(shop: str, location: str, inventory: Dict[str, List[Dict[str, Any]]]) -> None:
    if github_enabled():
        repo_path = inventory_repo_path(shop, location)
        _current, sha = github_load_json(repo_path, {})
        github_save_json(repo_path, inventory, f"Update {shop} {location} inventory", sha)
        return
    write_json(inventory_file(shop, location), inventory)


def load_history() -> List[Dict[str, Any]]:
    if github_enabled():
        try:
            data, _sha = github_load_json(GITHUB_HISTORY_FILE, [])
            if not isinstance(data, list):
                return []
            return dedupe_history_entries(data)
        except RuntimeError:
            pass
    return dedupe_history_entries(read_json(HISTORY_FILE, []))


def save_history(history: List[Dict[str, Any]]) -> None:
    history = dedupe_history_entries(history)
    if github_enabled():
        _current, sha = github_load_json(GITHUB_HISTORY_FILE, [])
        github_save_json(GITHUB_HISTORY_FILE, history, "Update BarMGR history", sha)
        return
    write_json(HISTORY_FILE, history)


def find_item(inventory: Dict[str, List[Dict[str, Any]]], category: str, item_name: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if category not in inventory:
        raise KeyError("Category not found")

    for item in inventory[category]:
        if item["name"] == item_name:
            return inventory[category], item

    raise KeyError("Item not found")


def parse_quantity(value: Any) -> int:
    quantity = int(value)
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero")
    return quantity


def history_timestamp() -> Dict[str, str]:
    now = datetime.now().astimezone()
    return {
        "timestamp": now.isoformat(timespec="seconds"),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
    }


def normalize_history_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    normalized = copy.deepcopy(entry)
    shop = normalized.get("shop")
    if isinstance(shop, str):
        try:
            normalized["shop"] = normalize_shop(shop)
        except ValueError:
            normalized["shop"] = shop.strip().lower()

    location = normalized.get("location")
    if isinstance(location, str):
        normalized_location = location.strip().lower()
        if normalized_location in VALID_LOCATIONS:
            normalized.setdefault("storage_location", normalized_location)
            if normalized.get("shop") in VALID_SHOPS:
                normalized["location"] = normalized["shop"]
            else:
                normalized["location"] = normalized_location

    return normalized


def history_entry_signature(entry: Dict[str, Any]) -> str:
    return json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def dedupe_history_entries(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen_signatures: set[str] = set()

    for entry in history:
        if not isinstance(entry, dict):
            continue
        normalized = normalize_history_entry(entry)
        signature = history_entry_signature(normalized)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        deduped.append(normalized)

    return deduped


def append_history_entry(entry: Dict[str, Any]) -> None:
    history = load_history()
    history.append({**history_timestamp(), "history_id": uuid.uuid4().hex, **entry})
    save_history(history)


def load_users() -> List[str]:
    seed_path = DATA_DIR / "users.py"
    return load_python_seed(seed_path, "USERS")


def json_response(handler: BaseHTTPRequestHandler, payload: Any, status: int = HTTPStatus.OK) -> None:
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def text_response(handler: BaseHTTPRequestHandler, data: bytes, content_type: str, status: int = HTTPStatus.OK) -> None:
    handler.send_response(status)
    handler.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def read_request_json(handler: BaseHTTPRequestHandler) -> Dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length else b"{}"
    return json.loads(raw.decode("utf-8"))


def safe_serve_file(handler: BaseHTTPRequestHandler, directory: Path, relative_path: str) -> None:
    file_path = (directory / relative_path).resolve()
    if not file_path.exists() or directory.resolve() not in file_path.parents and file_path != directory.resolve():
        handler.send_error(HTTPStatus.NOT_FOUND, "File not found")
        return

    content_type = "text/plain; charset=utf-8"
    suffix = file_path.suffix.lower()
    if suffix == ".html":
        content_type = "text/html; charset=utf-8"
    elif suffix == ".css":
        content_type = "text/css; charset=utf-8"
    elif suffix == ".js":
        content_type = "application/javascript; charset=utf-8"
    elif suffix == ".json":
        content_type = "application/json; charset=utf-8"
    elif suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}:
        content_type = f"image/{suffix[1:] if suffix != '.ico' else 'x-icon'}"

    text_response(handler, file_path.read_bytes(), content_type)


class BarMGRHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/":
            return safe_serve_file(self, ROOT, "index.html")

        if path.startswith("/templates/"):
            return safe_serve_file(self, TEMPLATES_DIR, path.removeprefix("/templates/"))

        if path.startswith("/static/"):
            return safe_serve_file(self, STATIC_DIR, path.removeprefix("/static/"))

        if path.startswith("/icons/"):
            return safe_serve_file(self, ICONS_DIR, path.removeprefix("/icons/"))

        if path == "/api/users":
            return json_response(self, {"users": load_users()})

        if path.startswith("/api/inventory/"):
            parts = path.strip("/").split("/")
            if len(parts) == 4:
                _, _, shop, location = parts
                try:
                    inventory = load_inventory(shop, location)
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return json_response(self, {"shop": shop, "location": location, "inventory": inventory})

        if path == "/api/history":
            return json_response(self, {"history": load_history()})

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path.startswith("/api/inventory/") and path.endswith("/adjust"):
            parts = path.strip("/").split("/")
            if len(parts) == 5:
                _, _, shop, location, _ = parts
                return self.handle_adjust(shop, location)

        if path == "/api/transfer":
            return self.handle_transfer()

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def handle_adjust(self, shop: str, location: str) -> None:
        try:
            payload = read_request_json(self)
            category = payload["category"]
            item_name = payload["item"]
            quantity_delta = int(payload["quantity"])
            user = payload.get("user", "Web")
            note = payload.get("note", "")
            location = normalize_location(location)
            shop = normalize_shop(shop)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return json_response(self, {"error": "Invalid request"}, HTTPStatus.BAD_REQUEST)

        if quantity_delta == 0:
            return json_response(self, {"error": "Quantity must not be zero"}, HTTPStatus.BAD_REQUEST)

        inventory = load_inventory(shop, location)

        try:
            _, item = find_item(inventory, category, item_name)
        except KeyError as exc:
            return json_response(self, {"error": str(exc)}, HTTPStatus.NOT_FOUND)

        new_quantity = item["quantity"] + quantity_delta
        if new_quantity < 0:
            return json_response(self, {"error": "Quantity cannot be lower than zero"}, HTTPStatus.BAD_REQUEST)

        old_quantity = item["quantity"]
        item["quantity"] = new_quantity
        save_inventory(shop, location, inventory)

        append_history_entry(
            {
                "user": user,
                "shop": shop,
                "action": "adjust",
                "location": location,
                "category": category,
                "item": item_name,
                "quantity": quantity_delta,
                "old_quantity": old_quantity,
                "new_quantity": new_quantity,
                "note": note,
            }
        )

        return json_response(
            self,
            {
                "message": "Inventory updated",
                "shop": shop,
                "location": location,
                "category": category,
                "item": item_name,
                "quantity": new_quantity,
            },
        )

    def handle_transfer(self) -> None:
        try:
            payload = read_request_json(self)
            shop = normalize_shop(payload["shop"])
            from_location = normalize_location(payload["from_location"])
            to_location = normalize_location(payload["to_location"])
            category = payload["category"]
            item_name = payload["item"]
            quantity = parse_quantity(payload["quantity"])
            user = payload.get("user", "Web")
            note = payload.get("note", "")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return json_response(self, {"error": "Invalid request"}, HTTPStatus.BAD_REQUEST)

        if from_location == to_location:
            return json_response(self, {"error": "Source and destination cannot be the same"}, HTTPStatus.BAD_REQUEST)

        from_inventory = load_inventory(shop, from_location)
        to_inventory = load_inventory(shop, to_location)

        try:
            _, from_item = find_item(from_inventory, category, item_name)
            _, to_item = find_item(to_inventory, category, item_name)
        except KeyError as exc:
            return json_response(self, {"error": str(exc)}, HTTPStatus.NOT_FOUND)

        if from_item["quantity"] < quantity:
            return json_response(self, {"error": "Quantity cannot be lower than zero"}, HTTPStatus.BAD_REQUEST)

        from_before = from_item["quantity"]
        to_before = to_item["quantity"]

        from_item["quantity"] -= quantity
        to_item["quantity"] += quantity

        save_inventory(shop, from_location, from_inventory)
        save_inventory(shop, to_location, to_inventory)

        append_history_entry(
            {
                "user": user,
                "shop": shop,
                "action": "transfer",
                "from_location": from_location,
                "to_location": to_location,
                "category": category,
                "item": item_name,
                "quantity": quantity,
                "from_before": from_before,
                "from_after": from_item["quantity"],
                "to_before": to_before,
                "to_after": to_item["quantity"],
                "note": note,
            }
        )

        return json_response(
            self,
            {
                "message": "Transfer completed",
                "shop": shop,
                "from_location": from_location,
                "to_location": to_location,
                "category": category,
                "item": item_name,
                "quantity": quantity,
            },
        )


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    ensure_data_files()
    server = ThreadingHTTPServer((host, port), BarMGRHandler)
    mode = "GitHub" if github_enabled() else "local"
    print(f"BarMGR running on http://{host}:{port} ({mode} storage)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
