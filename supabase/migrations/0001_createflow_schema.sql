-- CreateFlow schema: projects, generated assets, private storage.
-- Target: Supabase Postgres. Run in the SQL editor or via `supabase db push`.

-- ---------------------------------------------------------------------------
-- profiles (optional mirror of auth.users for display purposes)
-- ---------------------------------------------------------------------------
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own"
  on public.profiles for select
  using (auth.uid() = id);

drop policy if exists "profiles_insert_own" on public.profiles;
create policy "profiles_insert_own"
  on public.profiles for insert
  with check (auth.uid() = id);

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own"
  on public.profiles for update
  using (auth.uid() = id)
  with check (auth.uid() = id);

-- ---------------------------------------------------------------------------
-- projects: one row per creative brief
-- ---------------------------------------------------------------------------
create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,

  project_name text not null check (char_length(project_name) between 2 and 90),
  topic text not null check (char_length(topic) between 10 and 1200),
  audience text not null,
  goal text not null,
  tone text not null,
  presentation_type text not null default 'marketing'
    check (presentation_type in ('educational', 'business_pitch', 'marketing', 'portfolio', 'report')),
  presentation_length int not null default 8 check (presentation_length between 5 and 16),
  slide_count int not null default 0 check (slide_count >= 0),

  visual_style text not null default 'Editorial luxury',
  style_preset text not null default 'editorial_luxury'
    check (style_preset in ('editorial_luxury', 'modern_minimal', 'bold_creative',
                           'corporate_premium', 'dark_cinematic', 'playful_colorful')),

  primary_color text not null default '#3A2418',
  secondary_color text not null default '#E8DCC8',
  accent_color text,
  brand_name text not null default '',
  tagline text not null default '',
  extra_instructions text not null default '',

  brief_json jsonb not null default '{}'::jsonb,
  layouts_json jsonb not null default '[]'::jsonb,
  status text not null default 'ready'
    check (status in ('pending', 'generating', 'ready', 'failed')),

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists projects_user_created_idx
  on public.projects (user_id, created_at desc);

-- ---------------------------------------------------------------------------
-- generated_assets: one row per produced file
-- ---------------------------------------------------------------------------
create table if not exists public.generated_assets (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,

  kind text not null
    check (kind in ('presentation', 'poster', 'social', 'svg')),
  filename text not null,
  storage_path text not null,
  content_type text not null,
  size_bytes bigint not null check (size_bytes > 0),
  width_px int,
  height_px int,
  checksum text,
  created_at timestamptz not null default now()
);

create index if not exists assets_project_idx
  on public.generated_assets (project_id);
create index if not exists assets_user_idx
  on public.generated_assets (user_id);
create unique index if not exists assets_storage_path_unique
  on public.generated_assets (storage_path);

-- ---------------------------------------------------------------------------
-- updated_at maintenance
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists projects_set_updated_at on public.projects;
create trigger projects_set_updated_at
  before update on public.projects
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Row Level Security
-- The backend uses the service role key (bypasses RLS) after verifying the
-- caller's access token. These policies protect direct client access so a
-- leaked anon key cannot read another user's rows.
-- ---------------------------------------------------------------------------
alter table public.projects enable row level security;
alter table public.generated_assets enable row level security;

drop policy if exists "projects_select_own" on public.projects;
create policy "projects_select_own"
  on public.projects for select
  using (auth.uid() = user_id);

drop policy if exists "projects_insert_own" on public.projects;
create policy "projects_insert_own"
  on public.projects for insert
  with check (auth.uid() = user_id);

drop policy if exists "projects_update_own" on public.projects;
create policy "projects_update_own"
  on public.projects for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "projects_delete_own" on public.projects;
create policy "projects_delete_own"
  on public.projects for delete
  using (auth.uid() = user_id);

drop policy if exists "assets_select_own" on public.generated_assets;
create policy "assets_select_own"
  on public.generated_assets for select
  using (auth.uid() = user_id);

drop policy if exists "assets_insert_own" on public.generated_assets;
create policy "assets_insert_own"
  on public.generated_assets for insert
  with check (auth.uid() = user_id);

drop policy if exists "assets_delete_own" on public.generated_assets;
create policy "assets_delete_own"
  on public.generated_assets for delete
  using (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- Private storage bucket. Objects live at <user_id>/<project_id>/<file>
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'createflow-assets',
  'createflow-assets',
  false,
  26214400,
  array[
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'image/png',
    'image/jpeg',
    'image/webp',
    'image/svg+xml'
  ]
)
on conflict (id) do update
  set public = false,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "assets_read_own" on storage.objects;
create policy "assets_read_own"
  on storage.objects for select
  using (
    bucket_id = 'createflow-assets'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

drop policy if exists "assets_insert_own" on storage.objects;
create policy "assets_insert_own"
  on storage.objects for insert
  with check (
    bucket_id = 'createflow-assets'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

drop policy if exists "assets_delete_own" on storage.objects;
create policy "assets_delete_own"
  on storage.objects for delete
  using (
    bucket_id = 'createflow-assets'
    and (storage.foldername(name))[1] = auth.uid()::text
  );