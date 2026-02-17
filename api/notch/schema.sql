-- Notch schema (MVP)

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  handle TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at INTEGER NOT NULL,
  expires_at INTEGER,
  last_seen_at INTEGER
);

CREATE TABLE IF NOT EXISTS todo_lists (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_by TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  shared_with TEXT NOT NULL DEFAULT '[]',
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_todo_lists_owner ON todo_lists(created_by);

CREATE TABLE IF NOT EXISTS todos (
  id TEXT PRIMARY KEY,
  list_id TEXT,
  title TEXT NOT NULL,
  notes TEXT,
  done INTEGER NOT NULL DEFAULT 0,
  due_at INTEGER,
  remind_at INTEGER,
  remind_sent_at INTEGER,
  assigned_to TEXT REFERENCES users(id) ON DELETE SET NULL,
  shared_with TEXT NOT NULL DEFAULT '[]',
  created_by TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  deleted_at INTEGER,
  version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_todos_due ON todos(due_at);
CREATE INDEX IF NOT EXISTS idx_todos_remind ON todos(remind_at, remind_sent_at, done);

CREATE TABLE IF NOT EXISTS note_groups (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_by TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  shared_with TEXT NOT NULL DEFAULT '[]',
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_note_groups_owner ON note_groups(created_by);

CREATE TABLE IF NOT EXISTS notes (
  id TEXT PRIMARY KEY,
  group_id TEXT,
  title TEXT NOT NULL,
  body_md TEXT NOT NULL,
  shared_with TEXT NOT NULL DEFAULT '[]',
  created_by TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  deleted_at INTEGER,
  version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS outbox_notifications (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  topic TEXT NOT NULL,
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  click_url TEXT,
  priority INTEGER,
  tags TEXT,
  status TEXT NOT NULL,
  last_error TEXT,
  created_at INTEGER NOT NULL,
  sent_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox_notifications(status, created_at);

-- Public share links (anyone with link can view/edit depending on can_edit)
CREATE TABLE IF NOT EXISTS note_shares (
  token TEXT PRIMARY KEY,
  note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
  created_by TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  can_edit INTEGER NOT NULL DEFAULT 1,
  expires_at INTEGER,
  created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_note_shares_note ON note_shares(note_id);
CREATE INDEX IF NOT EXISTS idx_note_shares_exp ON note_shares(expires_at);
