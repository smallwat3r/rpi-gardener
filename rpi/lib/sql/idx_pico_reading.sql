CREATE INDEX IF NOT EXISTS pico_reading_idx ON pico_reading(recording_time DESC);
CREATE INDEX IF NOT EXISTS pico_reading_plant_idx ON pico_reading(plant_id, recording_time DESC);
