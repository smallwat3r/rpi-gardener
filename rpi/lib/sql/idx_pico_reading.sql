CREATE INDEX IF NOT EXISTS pico_reading_idx ON pico_reading(recording_time DESC);
CREATE INDEX IF NOT EXISTS pico_reading_cover_idx ON pico_reading(recording_time, plant_id, moisture);
