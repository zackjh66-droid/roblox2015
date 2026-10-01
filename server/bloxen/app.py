"""BLOXEN website + main API (FastAPI).

Pages reconstruct the July-2015 web experience from archived evidence
(see docs/WEBSITE.md). JSON API powers the Play flow, avatar, inventory,
catalog acquisition, favorites, friends, messages.
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import config, db, security

GRADES = {1: "original material", 2: "archived exact-date evidence",
          3: "archived near-date evidence", 4: "reconstruction from evidence",
          5: "inference"}

AVATAR_SLOTS = ["Hat", "Face", "Shirt", "Pants", "TShirt", "Head", "Gear", "Package"]
PALETTE = ["Bright red", "Bright blue", "Bright yellow", "Medium stone grey",
           "Bright green", "Br. yellowish orange", "Dark stone grey", "Reddish brown",
           "Institutional white", "Really black", "Pastel Blue", "Light orange"]

templates = Jinja2Templates(directory=str(config.WEB / "templates"))


def get_db() -> sqlite3.Connection:
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def slugify(name: str) -> str:
    out = []
    for ch in name.lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-") or "game"


def current_user(request: Request, con) -> dict | None:
    tok = request.cookies.get("BLOXENSESSION")
    if not tok:
        return None
    row = con.execute(
        """SELECT u.id, u.username, u.is_admin FROM sessions s
           JOIN users u ON u.id = s.user_id
           WHERE s.token_hash = ? AND s.expires_at > datetime('now') AND u.banned = 0""",
        (security.token_hash(tok),),
    ).fetchone()
    return dict(row) if row else None


def game_row(con, game_id) -> dict | None:
    g = con.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    if not g:
        return None
    d = dict(g)
    d["slug"] = slugify(d["name"])
    d["provenance_label"] = GRADES.get(int(d["provenance_grade"]), "?")
    return d


def build_app() -> FastAPI:
    app = FastAPI(title="BLOXEN", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=str(config.WEB / "static")), name="static")
    templates.env.auto_reload = True

    # ---------------------------------------------------------------- pages
    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        con = get_db()
        user = current_user(request, con)
        games = [game_row(con, r["id"]) for r in
                 con.execute("SELECT id FROM games ORDER BY id LIMIT 6")]
        games = [g for g in games if g]
        ctx = {"request": request, "user": user, "games": games,
               "friends": [], "recent": [], "avatar_thumb": None}
        if user:
            ctx["friends"] = [dict(r) for r in con.execute(
                """SELECT u.id, u.username FROM friendships f
                   JOIN users u ON u.id = CASE WHEN f.user_id = ? THEN f.friend_id ELSE f.user_id END
                   WHERE f.user_id = ? OR f.friend_id = ? LIMIT 6""",
                (user["id"], user["id"], user["id"]))]
            recent = []
            for r in con.execute(
                    "SELECT game_id, played_at FROM recently_played WHERE user_id = ? ORDER BY played_at DESC LIMIT 5",
                    (user["id"],)):
                g = game_row(con, r["game_id"])
                if g:
                    recent.append({"game": g, "played_at": r["played_at"]})
            ctx["recent"] = recent
        con.close()
        return templates.TemplateResponse(request, "home.html", ctx)

    @app.get("/games", response_class=HTMLResponse)
    def games_page(request: Request):
        con = get_db()
        user = current_user(request, con)
        games = [game_row(con, r["id"]) for r in con.execute("SELECT id FROM games ORDER BY id")]
        con.close()
        return templates.TemplateResponse(request, "games.html",
                                          {"request": request, "user": user, "games": [g for g in games if g]})

    @app.get("/games/{game_id}/{slug}", response_class=HTMLResponse)
    @app.get("/games/{game_id}", response_class=HTMLResponse)
    def game_details(request: Request, game_id: int, slug: str = ""):
        con = get_db()
        user = current_user(request, con)
        g = game_row(con, game_id)
        if not g:
            con.close()
            return RedirectResponse("/games", status_code=302)
        is_fav = False
        fav_count = con.execute(
            "SELECT COUNT(*) AS c FROM favorites WHERE target_type='game' AND target_id=?",
            (game_id,)).fetchone()["c"]
        if user:
            is_fav = bool(con.execute(
                "SELECT 1 FROM favorites WHERE user_id=? AND target_type='game' AND target_id=?",
                (user["id"], game_id)).fetchone())
        # asset stats
        stats = {"total": 0, "recovered": 0, "missing": 0}
        rows = con.execute(
            """SELECT a.status, COUNT(*) AS c FROM asset_dependencies d
               JOIN assets a ON a.id = d.asset_id WHERE d.game_id = ? GROUP BY a.status""",
            (game_id,)).fetchall()
        for r in rows:
            stats["total"] += r["c"]
            if r["status"] == "RECOVERED":
                stats["recovered"] = r["c"]
            else:
                stats["missing"] += r["c"]
        con.close()
        return templates.TemplateResponse(request, "game_details.html",
                                          {"request": request, "user": user, "game": g,
                                           "is_favorite": is_fav, "fav_count": fav_count,
                                           "asset_stats": stats})

    @app.post("/games/{game_id}/favorite")
    def game_favorite(request: Request, game_id: int):
        con = get_db()
        user = current_user(request, con)
        if user:
            hit = con.execute(
                "SELECT 1 FROM favorites WHERE user_id=? AND target_type='game' AND target_id=?",
                (user["id"], game_id)).fetchone()
            if hit:
                con.execute("DELETE FROM favorites WHERE user_id=? AND target_type='game' AND target_id=?",
                            (user["id"], game_id))
            else:
                con.execute("INSERT INTO favorites (user_id, target_type, target_id) VALUES (?, 'game', ?)",
                            (user["id"], game_id))
            con.commit()
        con.close()
        return RedirectResponse(f"/games/{game_id}", status_code=302)

    @app.get("/catalog", response_class=HTMLResponse)
    def catalog_page(request: Request, category: str = "All"):
        con = get_db()
        user = current_user(request, con)
        if category != "All":
            items = [dict(r) for r in con.execute(
                "SELECT * FROM items WHERE item_type = ? ORDER BY name", (category,))]
        else:
            items = [dict(r) for r in con.execute("SELECT * FROM items ORDER BY name")]
        for it in items:
            it["provenance_label"] = GRADES.get(int(it["provenance_grade"]), "?")
        cats = ["All"] + [r["item_type"] for r in con.execute(
            "SELECT DISTINCT item_type FROM items ORDER BY item_type")]
        con.close()
        return templates.TemplateResponse(request, "catalog.html",
                                          {"request": request, "user": user, "items": items,
                                           "categories": cats, "category": category})

    @app.get("/catalog/item.aspx", response_class=HTMLResponse)
    def catalog_item(request: Request, ID: int = 0):
        con = get_db()
        user = current_user(request, con)
        it = con.execute("SELECT * FROM items WHERE historical_asset_id = ?", (ID,)).fetchone()
        if not it:
            con.close()
            return RedirectResponse("/catalog", status_code=302)
        item = dict(it)
        item["provenance_label"] = GRADES.get(int(item["provenance_grade"]), "?")
        owned = False
        if user:
            owned = bool(con.execute(
                "SELECT 1 FROM inventory WHERE user_id=? AND item_id=?",
                (user["id"], item["id"])).fetchone())
        con.close()
        return templates.TemplateResponse(request, "catalog_item.html",
                                          {"request": request, "user": user, "item": item, "owned": owned})

    @app.post("/catalog/acquire")
    async def catalog_acquire(request: Request):
        form = await request.form()
        item_id = int(form.get("item_id", 0))
        con = get_db()
        user = current_user(request, con)
        if user:
            con.execute(
                "INSERT OR IGNORE INTO inventory (user_id, item_id, method) VALUES (?, ?, 'purchase')",
                (user["id"], item_id))
            con.commit()
        row = con.execute("SELECT historical_asset_id FROM items WHERE id=?", (item_id,)).fetchone()
        con.close()
        return RedirectResponse(f"/catalog/item.aspx?ID={row['historical_asset_id']}" if row else "/catalog",
                                status_code=302)

    @app.get("/User.aspx", response_class=HTMLResponse)
    def profile(request: Request, id: int = 0, username: str = ""):
        con = get_db()
        user = current_user(request, con)
        row = con.execute("SELECT * FROM users WHERE id = ?", (id,)).fetchone() if id else \
            con.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not row:
            con.close()
            return RedirectResponse("/", status_code=302)
        prof = con.execute("SELECT * FROM profiles WHERE user_id = ?", (row["id"],)).fetchone()
        profile_d = {"id": row["id"], "username": row["username"],
                     "blurb": (prof["blurb"] if prof else ""),
                     "join_date": (prof["join_date"] if prof else row["created_at"])}
        is_friend = False
        if user and user["id"] != row["id"]:
            is_friend = bool(con.execute(
                """SELECT 1 FROM friendships WHERE
                   (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)""",
                (user["id"], row["id"], row["id"], user["id"])).fetchone())
        favs = []
        for r in con.execute(
                "SELECT target_id FROM favorites WHERE user_id=? AND target_type='game'",
                (row["id"],)):
            g = game_row(con, r["target_id"])
            if g:
                favs.append(g)
        con.close()
        return templates.TemplateResponse(request, "profile.html",
                                          {"request": request, "user": user, "profile": profile_d,
                                           "is_friend": is_friend, "favorites": favs,
                                           "avatar_thumb": None})

    @app.get("/My/Character.aspx", response_class=HTMLResponse)
    def character(request: Request):
        con = get_db()
        user = current_user(request, con)
        if not user:
            con.close()
            return RedirectResponse("/Login.aspx", status_code=302)
        prof = con.execute("SELECT avatar_json FROM profiles WHERE user_id=?", (user["id"],)).fetchone()
        avatar = json.loads(prof["avatar_json"]) if prof else {}
        equipped = avatar.get("equipped", {})
        body_colors = avatar.get("body_colors",
                                 {p: "Bright blue" for p in
                                  ["Head", "Torso", "Left Arm", "Right Arm", "Left Leg", "Right Leg"]})
        wardrobe = []
        inv = con.execute(
            """SELECT i.* FROM inventory v JOIN items i ON i.id = v.item_id
               WHERE v.user_id = ? ORDER BY i.item_type, i.name""", (user["id"],)).fetchall()
        by_type: dict[str, list] = {}
        for r in inv:
            by_type.setdefault(r["item_type"], []).append(r)
        for slot in AVATAR_SLOTS:
            rows = by_type.get(slot, [])
            wardrobe.append({"slot": slot, "item_list": [
                {"id": r["id"], "name": r["name"],
                 "equipped": equipped.get(slot) == r["id"]} for r in rows]})
        con.close()
        return templates.TemplateResponse(request, "character.html",
                                          {"request": request, "user": user,
                                           "wardrobe": wardrobe, "body_colors": body_colors,
                                           "palette": PALETTE, "avatar_thumb": None})

    @app.post("/avatar/equip")
    def avatar_equip(request: Request, item_id: int = Form(...), slot: str = Form(...)):
        con = get_db()
        user = current_user(request, con)
        if user and slot in AVATAR_SLOTS:
            prof = con.execute("SELECT avatar_json FROM profiles WHERE user_id=?", (user["id"],)).fetchone()
            avatar = json.loads(prof["avatar_json"]) if prof else {}
            equipped = avatar.setdefault("equipped", {})
            if equipped.get(slot) == item_id:
                equipped.pop(slot, None)
            else:
                equipped[slot] = item_id
            con.execute("UPDATE profiles SET avatar_json=? WHERE user_id=?",
                        (json.dumps(avatar), user["id"]))
            con.commit()
        con.close()
        return RedirectResponse("/My/Character.aspx", status_code=302)

    @app.post("/avatar/colors")
    async def avatar_colors(request: Request):
        form = await request.form()
        con = get_db()
        user = current_user(request, con)
        if user:
            prof = con.execute("SELECT avatar_json FROM profiles WHERE user_id=?", (user["id"],)).fetchone()
            avatar = json.loads(prof["avatar_json"]) if prof else {}
            colors = avatar.setdefault("body_colors", {})
            for part in ["Head", "Torso", "Left Arm", "Right Arm", "Left Leg", "Right Leg"]:
                key = "color_" + part.replace(" ", "_")
                if key in form:
                    colors[part] = str(form[key])
            con.execute("UPDATE profiles SET avatar_json=? WHERE user_id=?",
                        (json.dumps(avatar), user["id"]))
            con.commit()
        con.close()
        return RedirectResponse("/My/Character.aspx", status_code=302)

    @app.get("/My/Stuff.aspx", response_class=HTMLResponse)
    def inventory(request: Request, category: str = "All", id: int = 0):
        con = get_db()
        user = current_user(request, con)
        owner_id = id or (user["id"] if user else 0)
        if not owner_id:
            con.close()
            return RedirectResponse("/Login.aspx", status_code=302)
        owner = con.execute("SELECT id, username FROM users WHERE id=?", (owner_id,)).fetchone()
        q = """SELECT i.* FROM inventory v JOIN items i ON i.id = v.item_id WHERE v.user_id = ?"""
        params: list = [owner_id]
        if category != "All":
            q += " AND i.item_type = ?"
            params.append(category)
        items = [dict(r) for r in con.execute(q + " ORDER BY i.item_type, i.name", params)]
        cats = ["All"] + [r["item_type"] for r in con.execute(
            "SELECT DISTINCT item_type FROM items ORDER BY item_type")]
        con.close()
        return templates.TemplateResponse(request, "inventory.html",
                                          {"request": request, "user": user, "items": items,
                                           "categories": cats, "category": category,
                                           "owner": dict(owner) if owner else {"username": "?"}})

    @app.get("/friends.aspx", response_class=HTMLResponse)
    def friends_page(request: Request, id: int = 0):
        con = get_db()
        user = current_user(request, con)
        owner_id = id or (user["id"] if user else 0)
        if not owner_id:
            con.close()
            return RedirectResponse("/Login.aspx", status_code=302)
        owner = con.execute("SELECT id, username FROM users WHERE id=?", (owner_id,)).fetchone()
        friends = [dict(r) for r in con.execute(
            """SELECT u.id, u.username FROM friendships f
               JOIN users u ON u.id = CASE WHEN f.user_id = ? THEN f.friend_id ELSE f.user_id END
               WHERE f.user_id = ? OR f.friend_id = ?""", (owner_id, owner_id, owner_id))]
        pending = []
        if user:
            pending = [dict(r) for r in con.execute(
                """SELECT u.id, u.username FROM friend_requests fr
                   JOIN users u ON u.id = fr.from_user
                   WHERE fr.to_user = ? AND fr.status = 'pending'""", (user["id"],))]
        con.close()
        return templates.TemplateResponse(request, "friends.html",
                                          {"request": request, "user": user, "friends": friends,
                                           "pending": pending,
                                           "owner": dict(owner) if owner else {"username": "?"}})

    @app.post("/friends/request")
    def friend_request(request: Request, user_id: int = Form(...)):
        con = get_db()
        user = current_user(request, con)
        if user and user["id"] != user_id:
            con.execute("INSERT OR IGNORE INTO friend_requests (from_user, to_user) VALUES (?, ?)",
                        (user["id"], user_id))
            con.commit()
        con.close()
        return RedirectResponse(f"/User.aspx?id={user_id}", status_code=302)

    @app.post("/friends/respond")
    def friend_respond(request: Request, user_id: int = Form(...), decision: str = Form(...)):
        con = get_db()
        user = current_user(request, con)
        if user:
            if decision == "accept":
                con.execute("UPDATE friend_requests SET status='accepted' WHERE from_user=? AND to_user=?",
                            (user_id, user["id"]))
                con.execute("INSERT OR IGNORE INTO friendships (user_id, friend_id) VALUES (?, ?)",
                            (user["id"], user_id))
                con.execute("INSERT OR IGNORE INTO friendships (user_id, friend_id) VALUES (?, ?)",
                            (user_id, user["id"]))
            else:
                con.execute("UPDATE friend_requests SET status='declined' WHERE from_user=? AND to_user=?",
                            (user_id, user["id"]))
            con.commit()
        con.close()
        return RedirectResponse("/friends.aspx", status_code=302)

    @app.get("/groups", response_class=HTMLResponse)
    def groups_page(request: Request):
        con = get_db()
        user = current_user(request, con)
        con.close()
        return templates.TemplateResponse(request, "groups.html",
                                          {"request": request, "user": user, "groups": []})

    @app.get("/develop", response_class=HTMLResponse)
    def develop_page(request: Request):
        con = get_db()
        user = current_user(request, con)
        games = [game_row(con, r["id"]) for r in con.execute("SELECT id FROM games")]
        con.close()
        return templates.TemplateResponse(request, "develop.html",
                                          {"request": request, "user": user,
                                           "games": [g for g in games if g]})

    @app.get("/My/Message.aspx", response_class=HTMLResponse)
    def messages_page(request: Request):
        con = get_db()
        user = current_user(request, con)
        if not user:
            con.close()
            return RedirectResponse("/Login.aspx", status_code=302)
        inbox = [dict(r) for r in con.execute(
            """SELECT m.*, u.username AS from_name FROM messages m
               JOIN users u ON u.id = m.from_user WHERE m.to_user = ? ORDER BY m.created_at DESC""",
            (user["id"],))]
        con.close()
        return templates.TemplateResponse(request, "messages.html",
                                          {"request": request, "user": user, "inbox": inbox})

    @app.post("/My/Message.aspx")
    def message_send(request: Request, to: str = Form(...), subject: str = Form(""),
                     body: str = Form("")):
        con = get_db()
        user = current_user(request, con)
        if user:
            dest = con.execute("SELECT id FROM users WHERE username = ?", (to,)).fetchone()
            if dest:
                con.execute(
                    "INSERT INTO messages (from_user, to_user, subject, body) VALUES (?,?,?,?)",
                    (user["id"], dest["id"], subject, body))
                con.commit()
        con.close()
        return RedirectResponse("/My/Message.aspx", status_code=302)

    @app.get("/search/results.aspx", response_class=HTMLResponse)
    def search(request: Request, Keyword: str = ""):
        con = get_db()
        user = current_user(request, con)
        like = f"%{Keyword}%"
        users = [dict(r) for r in con.execute(
            "SELECT id, username FROM users WHERE username LIKE ? LIMIT 20", (like,))]
        games = [game_row(con, r["id"]) for r in con.execute(
            "SELECT id FROM games WHERE name LIKE ? LIMIT 20", (like,))]
        items = [dict(r) for r in con.execute(
            "SELECT * FROM items WHERE name LIKE ? LIMIT 20", (like,))]
        con.close()
        return templates.TemplateResponse(request, "search.html",
                                          {"request": request, "user": user, "keyword": Keyword,
                                           "users": users, "games": [g for g in games if g], "items": items})

    @app.get("/bloom/about", response_class=HTMLResponse)
    def about(request: Request):
        con = get_db()
        user = current_user(request, con)
        con.close()
        return templates.TemplateResponse(request, "about.html", {"request": request, "user": user})

    # ------------------------------------------------------- auth (forms)
    @app.get("/Login.aspx", response_class=HTMLResponse)
    def login_page(request: Request):
        con = get_db()
        user = current_user(request, con)
        con.close()
        if user:
            return RedirectResponse("/", status_code=302)
        return templates.TemplateResponse(request, "login.html", {"request": request, "user": None})

    @app.post("/Login.aspx")
    def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
        con = get_db()
        row = con.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not row or not security.verify_password(password, row["password_hash"]):
            con.close()
            return templates.TemplateResponse(
                "login.html", {"request": request, "user": None,
                               "error": "Invalid username or password."}, status_code=401)
        tok = security.new_token()
        con.execute("INSERT INTO sessions (user_id, token_hash, expires_at) VALUES (?,?, datetime('now', '+7 days'))",
                    (row["id"], security.token_hash(tok)))
        con.execute("UPDATE users SET last_login_at = datetime('now') WHERE id = ?", (row["id"],))
        con.commit()
        con.close()
        resp = RedirectResponse("/", status_code=302)
        resp.set_cookie("BLOXENSESSION", tok, httponly=True, samesite="lax", max_age=7 * 86400)
        return resp

    @app.get("/Login/Logout.aspx")
    def logout(request: Request):
        con = get_db()
        tok = request.cookies.get("BLOXENSESSION")
        if tok:
            con.execute("DELETE FROM sessions WHERE token_hash = ?", (security.token_hash(tok),))
            con.commit()
        con.close()
        resp = RedirectResponse("/", status_code=302)
        resp.delete_cookie("BLOXENSESSION")
        return resp

    @app.get("/Register.aspx", response_class=HTMLResponse)
    def register_page(request: Request):
        return templates.TemplateResponse(request, "register.html", {"request": request, "user": None})

    @app.post("/Register.aspx")
    def register_submit(request: Request, username: str = Form(...), password: str = Form(...),
                        password2: str = Form(...)):
        con = get_db()
        err = None
        if len(username) < 3 or len(username) > 20 or not username.replace("_", "").isalnum():
            err = "Username must be 3-20 characters (letters, numbers, underscore)."
        elif password != password2:
            err = "Passwords do not match."
        elif len(password) < 8:
            err = "Password must be at least 8 characters."
        elif con.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            err = "Username already taken."
        if err:
            con.close()
            return templates.TemplateResponse(request, "register.html",
                                              {"request": request, "user": None, "error": err},
                                              status_code=400)
        cur = con.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, security.hash_password(password)))
        uid = cur.lastrowid
        con.execute("INSERT INTO profiles (user_id, join_date) VALUES (?, date('now'))", (uid,))
        con.commit()
        tok = security.new_token()
        con.execute("INSERT INTO sessions (user_id, token_hash, expires_at) VALUES (?,?, datetime('now', '+7 days'))",
                    (uid, security.token_hash(tok)))
        con.commit()
        con.close()
        resp = RedirectResponse("/", status_code=302)
        resp.set_cookie("BLOXENSESSION", tok, httponly=True, samesite="lax", max_age=7 * 86400)
        return resp

    @app.get("/My/Settings.aspx", response_class=HTMLResponse)
    def settings_page(request: Request, saved: int = 0):
        con = get_db()
        user = current_user(request, con)
        if not user:
            con.close()
            return RedirectResponse("/Login.aspx", status_code=302)
        prof = con.execute("SELECT * FROM profiles WHERE user_id=?", (user["id"],)).fetchone()
        con.close()
        return templates.TemplateResponse(request, "settings.html",
                                          {"request": request, "user": user,
                                           "profile": dict(prof) if prof else {"blurb": ""},
                                           "saved": saved})

    @app.post("/My/Settings.aspx")
    async def settings_submit(request: Request):
        con = get_db()
        user = current_user(request, con)
        if not user:
            con.close()
            return RedirectResponse("/Login.aspx", status_code=302)
        form = await request.form()
        if form.get("action") == "password" or (form.get("current") and form.get("new")):
            row = con.execute("SELECT password_hash FROM users WHERE id=?", (user["id"],)).fetchone()
            if row and security.verify_password(str(form.get("current", "")), row["password_hash"]):
                con.execute("UPDATE users SET password_hash=? WHERE id=?",
                            (security.hash_password(str(form["new"])), user["id"]))
                con.commit()
            return RedirectResponse("/My/Settings.aspx", status_code=302)
        con.execute("UPDATE profiles SET blurb=?, location=? WHERE user_id=?",
                    (str(form.get("blurb", "")), str(form.get("location", "")), user["id"]))
        con.commit()
        con.close()
        return RedirectResponse("/My/Settings.aspx?saved=1", status_code=302)

    # -------------------------------------------------------------- JSON API
    @app.get("/api/health")
    def api_health():
        return {"service": "bloxen-web", "ok": True}

    @app.post("/api/auth/register")
    async def api_register(request: Request):
        body = await request.json()
        username = str(body.get("username", ""))
        password = str(body.get("password", ""))
        if len(username) < 3 or len(password) < 8:
            return JSONResponse({"error": "invalid input"}, status_code=400)
        con = get_db()
        try:
            cur = con.execute("INSERT INTO users (username, password_hash) VALUES (?,?)",
                              (username, security.hash_password(password)))
            uid = cur.lastrowid
            con.execute("INSERT INTO profiles (user_id, join_date) VALUES (?, date('now'))", (uid,))
            con.commit()
        except sqlite3.IntegrityError:
            con.close()
            return JSONResponse({"error": "username taken"}, status_code=409)
        tok = security.new_token()
        con.execute("INSERT INTO sessions (user_id, token_hash, expires_at) VALUES (?,?, datetime('now', '+7 days'))",
                    (uid, security.token_hash(tok)))
        con.commit()
        con.close()
        return {"ok": True, "user_id": uid, "token": tok}

    @app.post("/api/auth/login")
    async def api_login(request: Request):
        body = await request.json()
        con = get_db()
        row = con.execute("SELECT * FROM users WHERE username = ?", (str(body.get("username", "")),)).fetchone()
        if not row or not security.verify_password(str(body.get("password", "")), row["password_hash"]):
            con.close()
            return JSONResponse({"error": "invalid credentials"}, status_code=401)
        tok = security.new_token()
        con.execute("INSERT INTO sessions (user_id, token_hash, expires_at) VALUES (?,?, datetime('now', '+7 days'))",
                    (row["id"], security.token_hash(tok)))
        con.commit()
        con.close()
        return {"ok": True, "user_id": row["id"], "token": tok}

    @app.get("/api/games")
    def api_games():
        con = get_db()
        games = [game_row(con, r["id"]) for r in con.execute("SELECT id FROM games")]
        con.close()
        return {"games": [g for g in games if g]}

    @app.get("/api/catalog")
    def api_catalog():
        con = get_db()
        items = [dict(r) for r in con.execute("SELECT * FROM items ORDER BY id")]
        con.close()
        return {"items": items}

    @app.post("/api/play/ticket")
    async def api_play_ticket(request: Request):
        """Issue a short-lived single-use launch ticket (see docs/PROTOCOL.md)."""
        body = await request.json()
        auth = request.headers.get("authorization", "")
        token = auth[7:] if auth.lower().startswith("bearer ") else body.get("token", "")
        con = get_db()
        row = con.execute(
            """SELECT u.id AS user_id FROM sessions s JOIN users u ON u.id = s.user_id
               WHERE s.token_hash = ? AND s.expires_at > datetime('now')""",
            (security.token_hash(token),)).fetchone()
        if not row:
            con.close()
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        game_id = int(body.get("game_id", 0))
        if not con.execute("SELECT 1 FROM games WHERE id=?", (game_id,)).fetchone():
            con.close()
            return JSONResponse({"error": "unknown game"}, status_code=404)
        ticket = security.new_ticket()
        con.execute(
            """INSERT INTO launch_tickets (ticket, user_id, game_id, server_id, expires_at)
               VALUES (?,?,?,?, datetime('now', ?))""",
            (security.token_hash(ticket), row["user_id"], game_id, body.get("server_id"),
             f"+{config.TICKET_TTL_SECONDS} seconds"))
        con.commit()
        con.close()
        return {"ticket": ticket, "expires_in": config.TICKET_TTL_SECONDS,
                "launch_uri": f"{config.PLAYER_URI_SCHEME}:play?ticket={ticket}&game={game_id}",
                "kind": "single-use"}

    @app.post("/api/play/validate")
    async def api_play_validate(request: Request):
        """Launcher-side ticket validation: single-use, TTL, user+game scoped."""
        body = await request.json()
        con = get_db()
        row = con.execute("SELECT * FROM launch_tickets WHERE ticket = ?",
                          (security.token_hash(str(body.get("ticket", ""))),)).fetchone()
        if not row:
            con.close()
            return JSONResponse({"error": "invalid ticket"}, status_code=400)
        if row["used_at"]:
            con.close()
            return JSONResponse({"error": "ticket already used (replay)"}, status_code=400)
        # compare in SQLite datetime space (both sides datetime('now') format)
        still_valid = con.execute(
            "SELECT 1 WHERE EXISTS (SELECT 1 FROM launch_tickets WHERE id=? AND expires_at > datetime('now'))",
            (row["id"],)).fetchone()
        if not still_valid:
            con.execute("UPDATE launch_tickets SET status='expired' WHERE id=?", (row["id"],))
            con.commit()
            con.close()
            return JSONResponse({"error": "ticket expired"}, status_code=400)
        game_id = int(body.get("game_id", 0))
        if game_id and row["game_id"] != game_id:
            con.close()
            return JSONResponse({"error": "wrong game"}, status_code=400)
        user_id = int(body.get("user_id", 0))
        if user_id and row["user_id"] != user_id:
            con.close()
            return JSONResponse({"error": "wrong user"}, status_code=400)
        con.execute("UPDATE launch_tickets SET used_at = datetime('now'), status='used' WHERE id=?",
                    (row["id"],))
        con.execute(
            """INSERT INTO recently_played (user_id, game_id) VALUES (?, ?)
               ON CONFLICT(user_id, game_id) DO UPDATE SET played_at = datetime('now')""",
            (row["user_id"], row["game_id"]))
        con.commit()
        game = game_row(con, row["game_id"])
        user = con.execute("SELECT id, username FROM users WHERE id=?", (row["user_id"],)).fetchone()
        con.close()
        return {"ok": True, "user": dict(user), "game": game,
                "server_id": row["server_id"]}

    return app


app = build_app()
