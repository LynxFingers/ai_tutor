# AI Tutor Bahasa Indonesia – Materi Berita (Flask + Supabase + Vercel)

## 1. Siapkan Supabase
1. Buat project baru di supabase.com (catat password database, pilih region terdekat, mis. Singapore).
2. Buka **SQL Editor → New query**, tempel isi `supabase/schema.sql`, klik **Run**.
3. Buka **Settings → API Keys**: salin **Project URL** dan **Secret key** (`sb_secret_...`).
   (Jika project masih memakai kunci lama, pakai `service_role` dari tab Legacy API Keys.)
   Jangan memakai publishable/anon key, dan jangan pernah menaruh secret key di kode atau GitHub.

## 2. Deploy ke Vercel
1. Upload folder ini ke repository GitHub (file `.env` tidak ikut karena ada di .gitignore).
2. Di vercel.com: **Add New → Project → import repository**. Framework terdeteksi Flask otomatis.
3. Sebelum Deploy, isi **Environment Variables**:
   | Nama | Isi |
   |---|---|
   | SUPABASE_URL | Project URL dari Supabase |
   | SUPABASE_SECRET_KEY | Secret key dari Supabase |
   | SECRET_KEY | teks acak panjang (untuk sesi login) |
   | KODE_GURU | kode rahasia untuk daftar akun guru |
4. Klik **Deploy**. Setiap perubahan environment variable butuh **Redeploy**.

## 3. Jalan lokal (opsional)
    pip install -r requirements.txt
    cp .env.example .env   # lalu isi nilainya
    python app.py          # http://localhost:5000

## Struktur
- `app.py` – aplikasi Flask (entrypoint Vercel), `db.py` – akses data ke Supabase
- `templates/` – halaman, `public/static/` – CSS dan materi.js (disajikan Vercel dari `public/`)
- Link absen/LKPD/evaluasi/video/rubrik: bagian KONFIGURASI di `app.py`
- Isi materi: `public/static/materi.js`

## Catatan keamanan
- Tabel memakai Row Level Security tanpa policy: hanya server (secret key) yang bisa membaca/menulis.
- Password disimpan dalam bentuk hash. Gunakan HTTPS (otomatis di Vercel).
