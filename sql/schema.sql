-- NoMansMovies — Supabase schema
-- Paste into the SQL editor of your Supabase project and run once.

-- ============ profiles ============
create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    username text unique not null,
    bio text default '',
    avatar_url text,
    color_scheme jsonb default '{"bg":"#0f0f14","fg":"#f0f0f5","accent":"#e50914"}'::jsonb,
    created_at timestamptz default now()
);

alter table public.profiles enable row level security;

drop policy if exists "profiles_select_authenticated" on public.profiles;
create policy "profiles_select_authenticated" on public.profiles
    for select using (auth.role() = 'authenticated');

drop policy if exists "profiles_insert_own" on public.profiles;
create policy "profiles_insert_own" on public.profiles
    for insert with check (auth.uid() = id);

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own" on public.profiles
    for update using (auth.uid() = id);

-- Auto-create a profile row when a new auth user signs up.
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
    insert into public.profiles (id, username)
    values (new.id, coalesce(new.raw_user_meta_data->>'username', 'user_' || substr(new.id::text, 1, 8)))
    on conflict (id) do nothing;
    return new;
end; $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

-- ============ friendships ============
create table if not exists public.friendships (
    id uuid primary key default gen_random_uuid(),
    requester uuid not null references public.profiles(id) on delete cascade,
    addressee uuid not null references public.profiles(id) on delete cascade,
    status text not null check (status in ('pending','accepted')) default 'pending',
    created_at timestamptz default now(),
    constraint friendship_unique unique (requester, addressee),
    constraint friendship_not_self check (requester <> addressee)
);

create index if not exists friendships_addressee_idx on public.friendships(addressee);
create index if not exists friendships_requester_idx on public.friendships(requester);

alter table public.friendships enable row level security;

drop policy if exists "friendships_select_participant" on public.friendships;
create policy "friendships_select_participant" on public.friendships
    for select using (auth.uid() = requester or auth.uid() = addressee);

drop policy if exists "friendships_insert_requester" on public.friendships;
create policy "friendships_insert_requester" on public.friendships
    for insert with check (auth.uid() = requester);

drop policy if exists "friendships_update_addressee" on public.friendships;
create policy "friendships_update_addressee" on public.friendships
    for update using (auth.uid() = addressee);

drop policy if exists "friendships_delete_participant" on public.friendships;
create policy "friendships_delete_participant" on public.friendships
    for delete using (auth.uid() = requester or auth.uid() = addressee);

-- ============ messages ============
create table if not exists public.messages (
    id uuid primary key default gen_random_uuid(),
    sender uuid not null references public.profiles(id) on delete cascade,
    recipient uuid not null references public.profiles(id) on delete cascade,
    body text not null,
    created_at timestamptz default now()
);

create index if not exists messages_pair_idx on public.messages(sender, recipient, created_at);

alter table public.messages enable row level security;

drop policy if exists "messages_select_participant" on public.messages;
create policy "messages_select_participant" on public.messages
    for select using (auth.uid() = sender or auth.uid() = recipient);

drop policy if exists "messages_insert_sender" on public.messages;
create policy "messages_insert_sender" on public.messages
    for insert with check (auth.uid() = sender);

-- Enable realtime for messages + friendships
alter publication supabase_realtime add table public.messages;
alter publication supabase_realtime add table public.friendships;

-- ============ avatars bucket ============
insert into storage.buckets (id, name, public)
values ('avatars', 'avatars', true)
on conflict (id) do nothing;

drop policy if exists "avatars_public_read" on storage.objects;
create policy "avatars_public_read" on storage.objects
    for select using (bucket_id = 'avatars');

drop policy if exists "avatars_owner_write" on storage.objects;
create policy "avatars_owner_write" on storage.objects
    for insert with check (
        bucket_id = 'avatars'
        and auth.uid()::text = (storage.foldername(name))[1]
    );

drop policy if exists "avatars_owner_update" on storage.objects;
create policy "avatars_owner_update" on storage.objects
    for update using (
        bucket_id = 'avatars'
        and auth.uid()::text = (storage.foldername(name))[1]
    );

drop policy if exists "avatars_owner_delete" on storage.objects;
create policy "avatars_owner_delete" on storage.objects
    for delete using (
        bucket_id = 'avatars'
        and auth.uid()::text = (storage.foldername(name))[1]
    );
