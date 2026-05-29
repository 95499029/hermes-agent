"""Hermes native download tool — aria2 RPC-backed.

Provides structured download function calling:
  - download_url:   Download a file via a URL (HTTP/FTP/S3/etc.)
  - download_status: Query status of an active/completed download
  - download_list:  List all active/queued downloads
  - download_stop:  Stop and remove a download from the queue
  - download_bt:    Add a BT torrent download
  - download_magnet: Add a BitTorrent magnet link download
  - download_history: Read the hermes-dl audit log

LLM-facing interface: these tools are registered via registry.register() and
dispatched by the model via function calling.  For human CLI access, use
`hermes-dl` (aria2 RPC wrapper) or AriaNg at http://localhost:6888.
The aria2 daemon must be running (launchd ai.hermes.aria2).
"""

import json
import logging
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

from hermes_constants import get_hermes_home

log = logging.getLogger(__name__)

# ── Default download directory ──────────────────────────────────────────────

def _default_download_dir() -> str:
    """Resolve ~/Downloads with fallback to HERMES_HOME/downloads."""
    home_dl = Path(os.path.expanduser("~/Downloads"))
    if home_dl.exists() and home_dl.is_dir():
        return str(home_dl)
    return str(get_hermes_home() / "downloads")

# ── Persistent state ────────────────────────────────────────────────────────

HISTORY_FILE = Path(os.environ.get(
    "HERMES_DL_HISTORY",
    str(get_hermes_home() / "downloads.jsonl")
))

# ── RPC endpoint ────────────────────────────────────────────────────────────

_ARIA2_SECRET = Path(os.environ.get(
    "HERMES_ARIA2_SECRET",
    str(get_hermes_home() / ".aria2_rpc_secret")
)).read_text().strip()
_RPC_URL = "http://localhost:6800/jsonrpc"


def _rpc(method: str, params: list) -> dict:
    """Fire a JSON-RPC call to aria2. Returns the 'result' dict or raises."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": [f"token:{_ARIA2_SECRET}"] + params,
    }).encode()

    req = urllib.request.Request(
        _RPC_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())
    if "error" in result:
        raise RuntimeError(f"aria2 RPC error: {result['error']}")
    return result["result"]


# ── Schema definitions ───────────────────────────────────────────────────────

DOWNLOAD_URL_SCHEMA = {
    "name": "download_url",
    "description": (
        "Download a file from a URL via aria2 RPC. "
        "Supports HTTP(S)/FTP/S3. Uses 16 connections by default. "
        "Returns the aria2 GID which can be used with download_status to track progress. "
        "File is saved to ~/Downloads unless dir= is specified."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Direct download URL. Must be a full URL (http:// or https://).",
            },
            "dir": {
                "type": "string",
                "description": "Download directory. Defaults to ~/Downloads.",
                "default": "/Users/ivan/Downloads",
            },
            "connections": {
                "type": "integer",
                "description": "Number of concurrent connections. Use 0 for auto-tune. Defaults to 16.",
                "default": 16,
                "minimum": 0,
            },
            "out": {
                "type": "string",
                "description": "Output filename. If omitted, aria2 uses the URL filename.",
            },
            "checksum": {
                "type": "string",
                "description": "Post-download checksum verification. Format: 'algorithm:hash' (e.g. 'sha-256:abc123...').",
            },
        },
        "required": ["url"],
    },
}

DOWNLOAD_STATUS_SCHEMA = {
    "name": "download_status",
    "description": (
        "Query the status of an active or completed download by its GID. "
        "Returns download progress, speed, size, and status (active/complete/error/removed)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "gid": {
                "type": "string",
                "description": "The aria2 GID returned by download_url.",
            },
        },
        "required": ["gid"],
    },
}

DOWNLOAD_HISTORY_SCHEMA = {
    "name": "download_history",
    "description": (
        "Query the hermes-dl download audit log (JSONL at ~/.hermes/downloads.jsonl). "
        "Each record contains: ts, url, filepath, size_bytes, duration_sec, connections, method. "
        "Returns the last N records in reverse chronological order."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of records to return. Defaults to 50.",
                "default": 50,
            },
        },
    },
}

DOWNLOAD_LIST_SCHEMA = {
    "name": "download_list",
    "description": (
        "List all active and queued downloads from aria2 RPC. "
        "Optionally filter by status: 'active', 'waiting', 'stopped', or 'all'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "Filter by download status.",
                "enum": ["active", "waiting", "stopped", "all"],
                "default": "all",
            },
        },
    },
}

DOWNLOAD_STOP_SCHEMA = {
    "name": "download_stop",
    "description": (
        "Stop and remove a download from aria2 queue by GID. "
        "The file is NOT deleted from disk — only removed from the queue. "
        "Completed files remain on disk."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "gid": {
                "type": "string",
                "description": "The aria2 GID returned by download_url.",
            },
        },
        "required": ["gid"],
    },
}

DOWNLOAD_BT_SCHEMA = {
    "name": "download_bt",
    "description": (
        "Add a BT torrent download via aria2 RPC. "
        "Accepts a .torrent file path on the local filesystem. "
        "aria2 will connect to DHT network and trackers automatically. "
        "Returns a GID for tracking with download_status. "
        "Completed files remain seeded according to aria2 seed settings."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "torrent_path": {
                "type": "string",
                "description": "Absolute path to the .torrent file on disk.",
            },
            "dir": {
                "type": "string",
                "description": "Download output directory. Defaults to ~/Downloads.",
            },
        },
        "required": ["torrent_path"],
    },
}

DOWNLOAD_MAGNET_SCHEMA = {
    "name": "download_magnet",
    "description": (
        "Add a BitTorrent magnet link download via aria2 RPC. "
        "aria2 will fetch metadata from DHT peers, then proceed like a normal BT download. "
        "Returns a GID for tracking with download_status. "
        "Note: DHT-only mode (no public trackers) may be slow depending on swarm size."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "magnet_uri": {
                "type": "string",
                "description": "Full magnet URI (starts with 'magnet:?').",
            },
            "dir": {
                "type": "string",
                "description": "Download output directory. Defaults to ~/Downloads.",
            },
        },
        "required": ["magnet_uri"],
    },
}

# ── Tool functions ────────────────────────────────────────────────────────────

def download_url_tool(url: str, dir: Optional[str] = None,
                      connections: int = 16, out: Optional[str] = None,
                      checksum: Optional[str] = None) -> str:
    """Submit a URL download to aria2 RPC."""
    if dir is None:
        dir = _default_download_dir()
    opts = {
        "dir": dir,
        "split": connections if connections > 0 else 16,
        "max-connection-per-server": min(connections, 16) if connections > 0 else 16,
    }
    if out:
        opts["out"] = out

    try:
        gid = _rpc("aria2.addUri", [[url], opts])
    except Exception as e:
        log.error("download_url failed: %s", e)
        return json.dumps({"error": str(e)})

    result = {
        "gid": gid,
        "url": url,
        "dir": dir,
        "connections": connections if connections > 0 else 16,
        "status": "queued",
        "message": f"Download queued with GID {gid}. Use download_status to track.",
    }
    if checksum:
        result["checksum"] = checksum
    return json.dumps(result)


def download_status_tool(gid: str) -> str:
    """Query aria2 for a specific download's status."""
    try:
        info = _rpc("aria2.tellStatus", [gid])
    except Exception as e:
        log.error("download_status failed: %s", e)
        return json.dumps({"error": str(e)})

    # Extract the most useful fields
    status = info.get("status", "unknown")
    total = int(info.get("totalLength", 0))
    completed = int(info.get("completedLength", 0))
    download_speed = info.get("downloadSpeed", "0")
    files = info.get("files", [])
    filenames = [Path(f["path"]).name for f in files] if files else []

    result = {
        "gid": gid,
        "status": status,
        "filename": filenames[0] if filenames else None,
        "total_bytes": total,
        "completed_bytes": completed,
        "progress_percent": round(completed / total * 100, 1) if total > 0 else 0,
        "speed_bps": int(download_speed),
        "speed_human": _human_speed(int(download_speed)),
    }
    return json.dumps(result)


def download_list_tool(status: str = "all") -> str:
    """List downloads, optionally filtered by status."""
    # tellActive: no params
    # tellWaiting/tellStopped: [offset, num]
    # "all" manually combines all three
    if status == "all":
        try:
            active = _rpc("aria2.tellActive", [])
            waiting = _rpc("aria2.tellWaiting", [0, 100])
            stopped = _rpc("aria2.tellStopped", [0, 100])
            items = active + waiting + stopped
        except Exception as e:
            log.error("download_list failed: %s", e)
            return json.dumps({"error": str(e)})
    else:
        method_map = {
            "active": ("aria2.tellActive", []),
            "waiting": ("aria2.tellWaiting", [0, 100]),
            "stopped": ("aria2.tellStopped", [0, 100]),
        }
        method, extra = method_map.get(status, ("aria2.tellActive", []))
        try:
            items = _rpc(method, extra)
        except Exception as e:
            log.error("download_list failed: %s", e)
            return json.dumps({"error": str(e)})

    downloads = []
    for info in items:
        files = info.get("files", [])
        filenames = [Path(f["path"]).name for f in files] if files else []
        downloads.append({
            "gid": info.get("gid"),
            "status": info.get("status"),
            "filename": filenames[0] if filenames else None,
            "total_bytes": int(info.get("totalLength", 0)),
            "completed_bytes": int(info.get("completedLength", 0)),
            "speed_bps": int(info.get("downloadSpeed", "0")),
            "speed_human": _human_speed(int(info.get("downloadSpeed", "0"))),
        })
    return json.dumps({"status": status, "count": len(downloads), "downloads": downloads})


def download_bt_tool(torrent_path: str, dir: Optional[str] = None) -> str:
    """Add a BT torrent via aria2 RPC."""
    if dir is None:
        dir = _default_download_dir()
    import base64
    expanded = os.path.expanduser(torrent_path)
    if not os.path.isfile(expanded):
        return json.dumps({"error": f"Torrent file not found: {torrent_path}"})
    try:
        with open(expanded, "rb") as f:
            torrent_b64 = base64.b64encode(f.read()).decode()
    except Exception as e:
        return json.dumps({"error": f"Failed to read torrent: {e}"})
    opts = {"dir": dir}
    try:
        gid = _rpc("aria2.addTorrent", [torrent_b64, [], opts])
    except Exception as e:
        log.error("download_bt failed: %s", e)
        return json.dumps({"error": str(e)})
    return json.dumps({
        "gid": gid,
        "torrent": torrent_path,
        "dir": dir,
        "status": "queued",
        "message": f"Torrent queued with GID {gid}. Use download_status to track.",
    })


def download_magnet_tool(magnet_uri: str, dir: Optional[str] = None) -> str:
    """Add a magnet link via aria2 RPC."""
    if dir is None:
        dir = _default_download_dir()
    opts = {"dir": dir}
    try:
        gid = _rpc("aria2.addUri", [[magnet_uri], opts])
    except Exception as e:
        log.error("download_magnet failed: %s", e)
        return json.dumps({"error": str(e)})
    return json.dumps({
        "gid": gid,
        "magnet": magnet_uri,
        "dir": dir,
        "status": "queued",
        "message": f"Magnet queued with GID {gid}. Use download_status to track.",
    })


def download_history_tool(limit: int = 50) -> str:
    """Read the last N records from the hermes-dl JSONL audit log."""
    if not HISTORY_FILE.exists():
        return json.dumps({"status": "ok", "count": 0, "records": [],
                          "message": "No history file yet (no downloads have completed)."})

    records = []
    try:
        with open(HISTORY_FILE) as f:
            lines = f.readlines()
        # Return in reverse chronological order (newest first)
        for line in reversed(lines[-limit:]):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                continue
    except Exception as e:
        log.error("download_history read failed: %s", e)
        return json.dumps({"error": str(e)})

    # Summarise size
    total_bytes = sum(r.get("size_bytes", 0) for r in records)
    return json.dumps({
        "status": "ok",
        "count": len(records),
        "total_bytes": total_bytes,
        "records": records,
    })


def download_stop_tool(gid: str) -> str:
    """Stop and remove a download by GID."""
    try:
        _rpc("aria2.remove", [gid])
    except Exception as e:
        log.error("download_stop failed: %s", e)
        return json.dumps({"error": str(e)})
    return json.dumps({"gid": gid, "status": "removed", "message": f"GID {gid} removed from queue."})


# ── Helpers ────────────────────────────────────────────────────────────────

def _human_speed(bps: float) -> str:
    if bps <= 0:
        return "0 B/s"
    for unit in ["B/s", "KB/s", "MB/s", "GB/s"]:
        if bps < 1024:
            return f"{bps:.1f} {unit}"
        bps /= 1024
    return f"{bps:.1f} GB/s"


# ── Registry ────────────────────────────────────────────────────────────────

from tools.registry import registry

registry.register(
    name="download_url",
    toolset="download",
    schema=DOWNLOAD_URL_SCHEMA,
    handler=lambda args, **kw: download_url_tool(
        url=args["url"],
        dir=args.get("dir"),
        connections=args.get("connections", 16),
        out=args.get("out"),
        checksum=args.get("checksum"),
    ),
    emoji="⬇️",
    max_result_size_chars=50_000,
)

registry.register(
    name="download_status",
    toolset="download",
    schema=DOWNLOAD_STATUS_SCHEMA,
    handler=lambda args, **kw: download_status_tool(gid=args["gid"]),
    emoji="📊",
    max_result_size_chars=50_000,
)

registry.register(
    name="download_list",
    toolset="download",
    schema=DOWNLOAD_LIST_SCHEMA,
    handler=lambda args, **kw: download_list_tool(status=args.get("status", "all")),
    emoji="📋",
    max_result_size_chars=50_000,
)

registry.register(
    name="download_stop",
    toolset="download",
    schema=DOWNLOAD_STOP_SCHEMA,
    handler=lambda args, **kw: download_stop_tool(gid=args["gid"]),
    emoji="⏹️",
    max_result_size_chars=10_000,
)

registry.register(
    name="download_bt",
    toolset="download",
    schema=DOWNLOAD_BT_SCHEMA,
    handler=lambda args, **kw: download_bt_tool(
        torrent_path=args["torrent_path"],
        dir=args.get("dir"),
    ),
    emoji="🪱",
    max_result_size_chars=10_000,
)

registry.register(
    name="download_history",
    toolset="download",
    schema=DOWNLOAD_HISTORY_SCHEMA,
    handler=lambda args, **kw: download_history_tool(limit=args.get("limit", 50)),
    emoji="📜",
    max_result_size_chars=80_000,
)

registry.register(
    name="download_magnet",
    toolset="download",
    schema=DOWNLOAD_MAGNET_SCHEMA,
    handler=lambda args, **kw: download_magnet_tool(
        magnet_uri=args["magnet_uri"],
        dir=args.get("dir"),
    ),
    emoji="🧲",
    max_result_size_chars=10_000,
)
