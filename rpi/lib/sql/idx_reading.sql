CREATE INDEX IF NOT EXISTS reading_idx ON reading(recording_time DESC);
CREATE INDEX IF NOT EXISTS reading_cover_idx ON reading(recording_time, temperature, humidity);
