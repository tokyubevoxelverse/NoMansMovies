-- NoMansMovies — Discord integration columns
-- Run AFTER schema.sql. Idempotent.

alter table public.profiles
    add column if not exists discord_id        text unique,
    add column if not exists discord_username  text,
    add column if not exists discord_avatar    text;

create index if not exists profiles_discord_id_idx on public.profiles(discord_id);
