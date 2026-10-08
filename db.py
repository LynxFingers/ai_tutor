"""Lapisan data Supabase (PostgREST lewat HTTPS). Tidak butuh koneksi Postgres langsung,
jadi aman dipakai di Vercel (serverless)."""
import os
from datetime import datetime, timezone, timedelta
import requests

WIB = timezone(timedelta(hours=7))
_session = requests.Session()


class DBError(Exception):
    pass


class Duplicate(DBError):
    pass


def _cfg():
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = (os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key:
        raise DBError("Konfigurasi Supabase belum diisi (SUPABASE_URL dan SUPABASE_SECRET_KEY).")
    return url, key


def rest(method, table, params=None, body=None, prefer=None):
    url, key = _cfg()
    h = {"apikey": key, "Content-Type": "application/json"}
    if key.startswith("eyJ"):               # kunci lama (service_role) berupa JWT
        h["Authorization"] = "Bearer " + key
    if prefer:
        h["Prefer"] = prefer
    try:
        r = _session.request(method, f"{url}/rest/v1/{table}", params=params, json=body, headers=h, timeout=15)
    except requests.RequestException as e:
        raise DBError("Tidak bisa terhubung ke Supabase: %s" % e)
    if r.status_code >= 400:
        try:
            err = r.json()
        except ValueError:
            err = {}
        if r.status_code == 409 or err.get("code") == "23505":
            raise Duplicate()
        raise DBError("Supabase error %s: %s" % (r.status_code, err.get("message") or r.text[:200]))
    return r.json() if r.text else None


def fetch_all(table, params):
    """Ambil semua baris (Supabase membatasi 1000 baris per permintaan)."""
    out, off = [], 0
    while True:
        p = dict(params, limit=1000, offset=off)
        page = rest("GET", table, p) or []
        out += page
        if len(page) < 1000:
            return out
        off += 1000


def fmt(ts):
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return d.astimezone(WIB).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return ts


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ---------- users ----------
def user_by_username(un):
    rows = rest("GET", "users", {"username": "eq." + un, "select": "*", "limit": 1})
    return rows[0] if rows else None


def create_user(nama, un, pw_hash, role):
    rows = rest("POST", "users", body={"nama": nama, "username": un, "password_hash": pw_hash,
                                       "role": role, "last_login": now_iso()},
                prefer="return=representation")
    return rows[0]


def touch_login(uid):
    rest("PATCH", "users", {"id": "eq.%d" % uid}, {"last_login": now_iso()}, "return=minimal")


# ---------- progress & pertanyaan ----------
def done_modul(uid):
    return [r["modul"] for r in rest("GET", "progress", {"user_id": "eq.%d" % uid, "select": "modul"}) or []]


def set_progress(uid, modul, done):
    if done:
        rest("POST", "progress", {"on_conflict": "user_id,modul"}, {"user_id": uid, "modul": modul},
             "resolution=ignore-duplicates,return=minimal")
    else:
        rest("DELETE", "progress", {"user_id": "eq.%d" % uid, "modul": "eq." + modul})


def add_question(uid, q):
    rest("POST", "questions", body={"user_id": uid, "q": q}, prefer="return=minimal")


# ---------- guru ----------
def kelas(modul_ids):
    siswa = fetch_all("users", {"role": "eq.siswa", "select": "id,nama,username,created_at,last_login"})
    prog = fetch_all("progress", {"select": "user_id,modul"})
    qs = fetch_all("questions", {"select": "user_id"})
    sel, tny, per = {}, {}, {m: 0 for m in modul_ids}
    for p in prog:
        sel[p["user_id"]] = sel.get(p["user_id"], 0) + 1
        if p["modul"] in per:
            per[p["modul"]] += 1
    for q in qs:
        tny[q["user_id"]] = tny.get(q["user_id"], 0) + 1
    rows = []
    for s in sorted(siswa, key=lambda x: x["nama"].lower()):
        rows.append({"id": s["id"], "nama": s["nama"], "username": s["username"],
                     "created_at": fmt(s["created_at"]), "last_login": fmt(s["last_login"]),
                     "selesai": sel.get(s["id"], 0), "tanya": tny.get(s["id"], 0)})
    return rows, [{"id": m, "n": per[m]} for m in modul_ids]


def siswa_detail(uid):
    rows = rest("GET", "users", {"id": "eq.%d" % uid, "role": "eq.siswa",
                                 "select": "id,nama,username,created_at,last_login", "limit": 1})
    if not rows:
        return None
    s = rows[0]
    s["created_at"], s["last_login"] = fmt(s["created_at"]), fmt(s["last_login"])
    qs = rest("GET", "questions", {"user_id": "eq.%d" % uid, "select": "q,created_at",
                                   "order": "id.desc", "limit": 50}) or []
    return s, done_modul(uid), [{"q": q["q"], "created_at": fmt(q["created_at"])} for q in qs]


def recent_questions(limit=40):
    rows = rest("GET", "questions", {"select": "q,created_at,users(nama)", "order": "id.desc", "limit": limit}) or []
    return [{"nama": (r.get("users") or {}).get("nama", "?"), "q": r["q"], "created_at": fmt(r["created_at"])} for r in rows]
