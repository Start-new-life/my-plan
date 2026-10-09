PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tasks (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  description   TEXT,
  priority      INTEGER NOT NULL CHECK (priority IN (1, 2, 3)),
  progress      INTEGER NOT NULL DEFAULT 0,
  target        INTEGER NOT NULL DEFAULT 1,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS goals (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  total         INTEGER NOT NULL,
  done          INTEGER NOT NULL DEFAULT 0,
  deadline      TEXT,
  unit          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS milestones (
  id            TEXT PRIMARY KEY,
  label         TEXT,
  target_date   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_logs (
  date              TEXT PRIMARY KEY,
  tasks_done        INTEGER,
  tasks_total       INTEGER,
  completion_pct    INTEGER,
  three_items_json  TEXT,
  three_done_json   TEXT,
  week_plan_text    TEXT,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS daily_task_checks (
  date     TEXT NOT NULL,
  task_id  TEXT NOT NULL,
  PRIMARY KEY (date, task_id),
  FOREIGN KEY (date) REFERENCES daily_logs(date) ON DELETE CASCADE,
  FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE TABLE IF NOT EXISTS drive_logs (
  date           TEXT NOT NULL,
  goal_id        TEXT NOT NULL,
  session_count  INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (date, goal_id),
  FOREIGN KEY (date) REFERENCES daily_logs(date) ON DELETE CASCADE,
  FOREIGN KEY (goal_id) REFERENCES goals(id)
);

CREATE TABLE IF NOT EXISTS focus_logs (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  date       TEXT NOT NULL,
  minutes    INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (date) REFERENCES daily_logs(date) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ui_state (
  key    TEXT PRIMARY KEY,
  value  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS weekly_reviews (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  week_start      TEXT NOT NULL UNIQUE,
  week_end        TEXT NOT NULL,
  metrics_json    TEXT NOT NULL DEFAULT '{}',
  prose           TEXT NOT NULL DEFAULT '',
  source_ids_json TEXT,
  created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conversations (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  title       TEXT,
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id  INTEGER NOT NULL,
  role             TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content          TEXT NOT NULL,
  source_ids_json  TEXT,
  created_at       TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_daily_task_checks_task ON daily_task_checks(task_id);
CREATE INDEX IF NOT EXISTS idx_drive_logs_goal ON drive_logs(goal_id);
CREATE INDEX IF NOT EXISTS idx_focus_logs_date ON focus_logs(date);
