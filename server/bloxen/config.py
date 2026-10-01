"""BLOXEN configuration: paths, ports, target era constants."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # repo root
DATA = ROOT / "data"
WEB = ROOT / "web"
RESEARCH = ROOT / "research"
QUARANTINE = ROOT / "quarantine"
CHECKPOINTS = ROOT / "checkpoints"

DATA.mkdir(exist_ok=True)
QUARANTINE.mkdir(exist_ok=True)

# --- Target era constants (see docs/CLIENT.md for provenance) ---
TARGET_DATE = "2015-07-23"
TARGET_WINDOWS_PLAYER_VERSION = "0.205.0.61876"
TARGET_WINDOWS_PLAYER_GUID = "version-0d46087630eb46cd"
# SHA-256 claimed for RobloxPlayerBeta.exe in prior research; independently re-verify when a
# real package can be obtained (see docs/CLIENT.md -> "Hash verification status").
TARGET_WINDOWS_PLAYER_SHA256_CLAIMED = (
    "384a4cb38de6977899e09e59c2136619fef521dc7b4adeb34d404945120c8a44"
)
API_DUMP_PATH = RESEARCH / "sources" / "build-archive" / TARGET_WINDOWS_PLAYER_GUID / "API-Dump.json"

# --- Services ---
WEB_HOST = os.environ.get("BLOXEN_WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.environ.get("BLOXEN_WEB_PORT", "8080"))
COMPAT_HOST = os.environ.get("BLOXEN_COMPAT_HOST", "127.0.0.1")   # private by default
COMPAT_PORT = int(os.environ.get("BLOXEN_COMPAT_PORT", "8081"))
ASSET_HOST = os.environ.get("BLOXEN_ASSET_HOST", "127.0.0.1")     # private by default
ASSET_PORT = int(os.environ.get("BLOXEN_ASSET_PORT", "8082"))
GAMESERVER_HOST = os.environ.get("BLOXEN_GS_HOST", "127.0.0.1")
GAMESERVER_PORT = int(os.environ.get("BLOXEN_GS_PORT", "53640"))   # classic Roblox game port

# --- Databases ---
DB_PATH = DATA / "bloxen.db"
RESEARCH_DB_PATH = RESEARCH / "db" / "research.sqlite3"

# --- 2015 client protocol constants (reconstruction; see docs/PROTOCOL.md) ---
PROTOCOL_VERSION = 31
RAKNET_MAGIC = b"\x00\xff\xff\x00\xfe\xfe\xfe\xfe\xfd\xfd\xfd\xfd\x12\x34\x56\x78"

# --- Launcher ---
TICKET_TTL_SECONDS = 120
PLAYER_URI_SCHEME = "bloxen-player"

BLOXEN_BRAND = "BLOXEN"
BLOXEN_TAGLINE = ("An unofficial preservation reconstruction of the July 2015 Roblox "
                  "experience. Not affiliated with Roblox Corporation.")
