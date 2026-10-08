-- Jalankan di Supabase: SQL Editor -> New query -> tempel -> Run

create table if not exists public.users (
  id            bigint generated always as identity primary key,
  nama          text not null,
  username      text not null unique,
  password_hash text not null,
  role          text not null check (role in ('siswa','guru')),
  created_at    timestamptz not null default now(),
  last_login    timestamptz
);

create table if not exists public.progress (
  user_id bigint not null references public.users(id) on delete cascade,
  modul   text   not null,
  primary key (user_id, modul)
);

create table if not exists public.questions (
  id         bigint generated always as identity primary key,
  user_id    bigint not null references public.users(id) on delete cascade,
  q          text   not null,
  created_at timestamptz not null default now()
);

-- Keamanan: aktifkan RLS TANPA policy => kunci publik (publishable/anon) tidak bisa
-- membaca/menulis. Hanya server (secret key) yang bisa mengakses data.
alter table public.users     enable row level security;
alter table public.progress  enable row level security;
alter table public.questions enable row level security;
