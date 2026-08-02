-- CyberGuard multi third-party binding support (additive only).
-- Each user may bind more than one third-party identity (GitHub AND Google).
-- oauth_provider / oauth_subject remain as the "primary" (latest) binding,
-- oauth_bindings stores the full list: [{"provider": "github", "subject": "..."}, ...]

ALTER TABLE users ADD COLUMN oauth_bindings TEXT NULL COMMENT '全部第三方绑定 JSON 数组' AFTER oauth_subject;

-- Backfill existing single bindings into the new column.
UPDATE users
SET oauth_bindings = JSON_ARRAY(JSON_OBJECT('provider', oauth_provider, 'subject', oauth_subject))
WHERE oauth_provider IS NOT NULL AND oauth_bindings IS NULL;
