import os
import re
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, abort)
from werkzeug.security import generate_password_hash, check_password_hash
import db

BASE = os.path.dirname(os.path.abspath(__file__))
# Lokal: baca file .env (jika ada). Di Vercel: pakai Environment Variables.
_env = os.path.join(BASE, ".env")
if os.path.exists(_env):
    for line in open(_env, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# ================= KONFIGURASI =================
KODE_GURU = os.environ.get("KODE_GURU", "GURU2026")   # kode untuk daftar akun guru
LINKS = {
    "absen": "https://docs.google.com/forms/d/e/1FAIpQLSeWF9CAm0sEKZ08VFfXkUOfP1PlJ71mLNCwfajKRwySLx7MEg/viewform?usp=header",
    "lkpd": "https://wayground.com/join?gc=48957805",
    "evaluasi": "https://wayground.com/join?gc=60289389",
    "video": "https://youtu.be/VAJgnAw1jmk?si=HJIrL7Ng4ctAmrQW",
    "rubrik": "https://docs.google.com/spreadsheets/d/1G6E7D106PlvNTO9iNGTfg36TtFcboKACJXY6XF-Wp_Y/edit?usp=drivesdk",  # khusus guru
}
# Identitas kelompok: tampil di halaman login, dashboard siswa, dan dashboard guru.
# Kosongkan salah satu isian (mis. "kelas": "") jika tidak ingin ditampilkan.
IDENTITAS = {
    "kelompok": "Kelompok ...",                 # contoh: "Kelompok 3"
    "anggota": ["Nama Anggota 1", "Nama Anggota 2", "Nama Anggota 3"],
    "kelas": "Kelas ...",                       # contoh: "PBI 5A"
    "institusi": "Nama Sekolah / Kampus ...",
}
SISWA_ITEMS = [("beranda", "🏠", "Beranda"), ("panduan", "📖", "Panduan"), ("modul", "📚", "Modul"), ("tanya", "🤖", "Tanya AI")]
GURU_ITEMS = [("ringkasan", "🏠", "Ringkasan"), ("pelaksanaan", "📋", "Modul Ajar"), ("kelas", "👥", "Isi Kelas"), ("tanya", "💬", "Pertanyaan"), ("rubrik", "📊", "Rubrik")]
MODUL_IDS = ["tujuan", "pengertian", "struktur", "unsur", "kaidah", "jenis", "faktaopini", "cara",
             "bandingkan", "pengalaman", "etika", "contoh", "lkpd", "evaluasi"]
# ===============================================


def youtube_id(url):
    """Ambil ID video dari tautan YouTube (youtu.be, watch?v=, embed/, shorts/)."""
    m = re.search(r"(?:youtu\.be/|v=|/embed/|/shorts/)([A-Za-z0-9_-]{11})", url or "")
    return m.group(1) if m else ""

# static_folder di public/static agar sama dengan yang disajikan Vercel (/static/...)
app = Flask(__name__, static_folder=os.path.join(BASE, "public", "static"), static_url_path="/static")
if os.environ.get("VERCEL") and not os.environ.get("SECRET_KEY"):
    raise RuntimeError("SECRET_KEY belum diisi di Environment Variables Vercel.")
app.secret_key = os.environ.get("SECRET_KEY") or "kunci-lokal-hanya-untuk-uji-coba"
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=bool(os.environ.get("VERCEL")),
                  PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 30)


@app.context_processor
def inject_identitas():
    return {"ident": IDENTITAS}


@app.errorhandler(db.DBError)
def db_error(e):
    return render_template("error.html", pesan=str(e)), 500


def current_user():
    if not session.get("uid"):
        return None
    return {"id": session["uid"], "nama": session.get("nama", "?"),
            "username": session.get("username", ""), "role": session.get("role", "siswa")}


def login_session(u):
    session.clear()
    session.permanent = True
    session.update(uid=u["id"], nama=u["nama"], username=u["username"], role=u["role"])


def role_required(role):
    def deco(f):
        @wraps(f)
        def wrap(*a, **k):
            u = current_user()
            if not u:
                return redirect(url_for("login"))
            if u["role"] != role:
                return redirect(url_for("index"))
            return f(u, *a, **k)
        return wrap
    return deco


@app.route("/")
def index():
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    return redirect(url_for("guru" if u["role"] == "guru" else "siswa"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        un = request.form.get("username", "").strip().lower()
        u = db.user_by_username(un)
        if u and check_password_hash(u["password_hash"], request.form.get("password", "")):
            login_session(u)
            db.touch_login(u["id"])
            return redirect(url_for("index"))
        flash("Username atau password salah.", "err")
    return render_template("login.html", mode="login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nama = request.form.get("nama", "").strip()
        un = request.form.get("username", "").strip().lower()
        pw = request.form.get("password", "")
        role = request.form.get("role", "siswa")
        if role not in ("siswa", "guru"):
            role = "siswa"
        if not nama or not un or len(pw) < 6:
            flash("Lengkapi data. Password minimal 6 karakter.", "err")
        elif not un.replace("_", "").replace(".", "").isalnum():
            flash("Username hanya boleh huruf, angka, titik, dan garis bawah.", "err")
        elif role == "guru" and request.form.get("kode", "") != KODE_GURU:
            flash("Kode guru salah.", "err")
        elif db.user_by_username(un):
            flash("Username sudah dipakai.", "err")
        else:
            try:
                u = db.create_user(nama, un, generate_password_hash(pw), role)
            except db.Duplicate:
                flash("Username sudah dipakai.", "err")
            else:
                login_session(u)
                return redirect(url_for("index"))
    return render_template("login.html", mode="register")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------- DASHBOARD ----------------
@app.route("/siswa")
@role_required("siswa")
def siswa(u):
    extra = [("📝", "Absen", LINKS["absen"]), ("🧩", "LKPD", LINKS["lkpd"]), ("✅", "Evaluasi", LINKS["evaluasi"])]
    return render_template("siswa.html", user=u, video_id=youtube_id(LINKS["video"]), done=db.done_modul(u["id"]),
                           links={k: v for k, v in LINKS.items() if k != "rubrik"}, items=SISWA_ITEMS,
                           extra=extra, cta=("Lanjutkan Belajar", "modul"),
                           title="Belajar Berita", subtitle="Dashboard Siswa")


@app.route("/guru")
@role_required("guru")
def guru(u):
    return render_template("guru.html", user=u, total_modul=len(MODUL_IDS), links=LINKS, items=GURU_ITEMS,
                           extra=[("📊", "Rubrik Penilaian", LINKS["rubrik"])], cta=("Lihat Isi Kelas", "kelas"),
                           rubrik_embed=LINKS["rubrik"].split("/edit")[0] + "/edit?rm=minimal",
                           title="Kelas Berita", subtitle="Dashboard Guru")


# ---------------- API ----------------
@app.route("/api/progress", methods=["POST"])
@role_required("siswa")
def api_progress(u):
    d = request.get_json(silent=True) or {}
    if d.get("modul") not in MODUL_IDS:
        abort(400)
    db.set_progress(u["id"], d["modul"], bool(d.get("done")))
    return jsonify(ok=True)


@app.route("/api/tanya", methods=["POST"])
@role_required("siswa")
def api_tanya(u):
    q = ((request.get_json(silent=True) or {}).get("q") or "").strip()[:300]
    if q:
        db.add_question(u["id"], q)
    return jsonify(ok=True)


@app.route("/api/kelas")
@role_required("guru")
def api_kelas(u):
    rows, per = db.kelas(MODUL_IDS)
    return jsonify(total_modul=len(MODUL_IDS), siswa=rows, per_modul=per)


@app.route("/api/pertanyaan")
@role_required("guru")
def api_pertanyaan(u):
    return jsonify(pertanyaan=db.recent_questions())


@app.route("/api/siswa/<int:uid>")
@role_required("guru")
def api_siswa(u, uid):
    r = db.siswa_detail(uid)
    if not r:
        abort(404)
    s, done, qs = r
    return jsonify(siswa=s, selesai=done, pertanyaan=qs)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
