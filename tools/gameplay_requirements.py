"""Per-game scripting / gameplay-logic requirements analysis.

STATIC ANALYSIS ONLY: reads script source text from the quarantined place files to
classify which runtime features each game requires. Nothing is executed — scripts stay
inert data (intake rule).

Writes: research/db/gameplay_requirements.json
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

FEATURE_PATTERNS = [
    (r"GetService\(\s*[\"']Players[\"']\s*\)|Players\.", "Players service"),
    (r"PlayerAdded|CharacterAdded|\.Character\b", "character lifecycle"),
    (r"RemoteEvent|RemoteFunction|FireServer|FireClient|OnServerEvent|OnClientEvent|InvokeServer|InvokeClient", "client/server remotes"),
    (r"FilteringEnabled", "FilteringEnabled semantics"),
    (r"\bwait\s*\(|\bspawn\s*\(|\bdelay\s*\(|\btick\s*\(", "task scheduler"),
    (r"BodyPosition|BodyVelocity|BodyGyro|BodyForce|BodyThrust|BodyAngularVelocity", "legacy BodyMovers"),
    (r"VehicleSeat|GetPropertyChangedSignal\(\"Throttle\"|\.Steer", "vehicle physics"),
    (r"Humanoid|MoveTo|Jump|WalkSpeed|TakeDamage", "Humanoid + movement"),
    (r"LoadCharacter|RespawnLocation|TeamColor|Neutral", "spawn/respawn"),
    (r"Debris:AddItem|Instance\.new", "instance management"),
    (r"math\.|Vector3\.new|CFrame\.new|UDim2\.new", "math libraries"),
    (r"HttpService|HttpGet|HttpPost|GetAsync\(|PostAsync", "HTTP (must be sandboxed/none)"),
    (r"DataStoreService|GetAsync|SetAsync|UpdateAsync|datastores?", "DataStore persistence"),
    (r"BadgeService|AwardBadge", "BadgeService"),
    (r"GamePassService|ProcessReceipt|MarketplaceService|DeveloperProduct", "commerce callbacks"),
    (r"Sound|:Play\(\)|:Stop\(\)|SoundService", "audio playback"),
    (r"CollectionService", "CollectionService tags"),
    (r"PointLight|SpotLight|Fire|Smoke|Sparkles|ParticleEmitter|Explosion", "effects"),
    (r"SurfaceGui|BillboardGui|TextLabel|TextButton|ImageLabel|ScreenGui|StarterGui", "GUI"),
    (r"TweenService|TweenPosition|TweenSize", "tweening"),
    (r"\brequire\s*\(", "ModuleScript require chain"),
    (r"WaitForChild|FindFirstChild|FindFirstClass", "instance lookup"),
    (r"Chat|Talk|BubbleChat", "chat integration"),
    (r"GetMouse|UserInputService|ContextActionService|KeyDown|Mouse\.|mouse\.", "input handling"),
    (r"Camera|CurrentCamera", "camera manipulation"),
    (r"Teams|Neutral|\.Team\b", "teams"),
    (r"leaderstats|Leaderstats", "leaderstats"),
]

GAMES = {
    "Work at a Pizza Place (2014L).rbxl": "Work at a Pizza Place",
    "Speed Run 4 (1st part).rbxl": "Speed Run 4",
    "Welcome to the Town of Robloxia.rbxl": "Welcome to the Town of Robloxia",
    "The Normal Elevator - Fixed for 2015M.rbxl": "The Normal Elevator",
    "Mad Games (v1.3b, 2015).rbxl": "Mad Games",
    "Flood Escape (July 8th, 2015, V1.6.5).rbxl": "Flood Escape",
    "Natural Disaster Survival.rbxl": "Natural Disaster Survival",
}

PILLARS = {
    "Work at a Pizza Place": ["pizza-making state machine", "team/job assignment",
                              "building tools", "money/balance persistence",
                              "customer AI", "doors/interactives"],
    "Speed Run 4": ["stage checkpoints", "timer", "leaderstats", "kill/reset bricks",
                    "stage teleporting"],
    "Welcome to the Town of Robloxia": ["job system", "day/night + disaster cycle",
                                        "house ownership", "tools"],
    "The Normal Elevator": ["elevator state machine", "floor selection", "minigame rounds",
                            "cutscene GUIs"],
    "Mad Games": ["minigame rotation", "round timer", "loadout", "score/leaderstats"],
    "Flood Escape": ["rising water simulation", "map rotation", "buttons/levers",
                     "checkpoint stages", "difficulty voting"],
    "Natural Disaster Survival": ["disaster scheduler",
                                  "per-disaster physics (meteor/flood/tornado)",
                                  "map rotation", "round reset", "survival scoring",
                                  "Person299 admin-commands script stays inert forever"],
}


def iter_script_sources(place_path: Path):
    """Yield (name, class, source_bytes) for every script in the place — read-only.

    Scripts are NEVER executed here; source text is read only to statically
    classify required runtime features (intake rule: scripts as inert data).
    """
    from bloxen.importer.rbxl_binary import parse_binary
    from bloxen.importer.rbxlx_xml import parse_xml

    data = place_path.read_bytes()
    if data[:16].startswith(b"<roblox!") and b"\x89\xff" in data[:16]:
        report = parse_binary(data)
    else:
        report = parse_xml(data)
    for inst in report["instances"].values():
        cls = getattr(inst, "class_name", "")
        if cls not in ("Script", "LocalScript", "ModuleScript"):
            continue
        props = getattr(inst, "properties", {})
        src = props.get("Source", b"")
        if isinstance(src, str):
            src = src.encode("utf-8", "replace")
        yield getattr(inst, "name", "?"), cls, src


def main() -> None:
    con = sqlite3.connect(ROOT / "data" / "bloxen.db")
    out = []
    for src, si_raw in con.execute(
            "select source_path, script_inventory from place_imports"):
        fname = Path(src).name
        game = GAMES.get(fname)
        if not game:
            continue
        inv = json.loads(si_raw)
        features = set()
        total_src = 0
        try:
            for name, cls, body in iter_script_sources(Path(src)):
                total_src += len(body)
                text = body.decode("utf-8", "replace")
                for pat, feat in FEATURE_PATTERNS:
                    if re.search(pat, text, re.I):
                        features.add(feat)
        except Exception as e:  # parse hiccup -> record, don't crash the analysis
            features.add(f"(static scan error: {e})")
        req = {
            "game": game,
            "place_file": fname,
            "script_count": len(inv),
            "script_source_bytes_scanned": total_src,
            "required_logic_pillars": PILLARS.get(game, []),
            "runtime_features_detected_in_source": sorted(features),
            "status": "parsed / metadata-ok — game logic NOT running",
            "playable_claim": False,
            "reason": ("scripts inventoried as inert data only; no reviewed, sandboxed "
                       "execution path exists yet — cannot honestly claim playable"),
        }
        out.append(req)

    db_out = ROOT / "research" / "db" / "gameplay_requirements.json"
    db_out.write_text(json.dumps(out, indent=2))
    print(f"wrote {db_out} ({len(out)} games)")
    for r in out:
        print(f"  {r['game']}: {r['script_count']} scripts / "
              f"{r['script_source_bytes_scanned']} source bytes scanned / "
              f"{len(r['runtime_features_detected_in_source'])} features / "
              f"playable={r['playable_claim']}")


if __name__ == "__main__":
    main()
