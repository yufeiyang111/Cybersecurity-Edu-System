-- Per-user chat font size (additive only).
ALTER TABLE user_preferences
    ADD COLUMN font_size VARCHAR(20) NOT NULL DEFAULT 'medium' AFTER font_family;
