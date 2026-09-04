-- No covering index: it would duplicate every row, doubling SD card writes per
-- insert. The chart, stats and latest queries only need the time index.
CREATE INDEX IF NOT EXISTS pico_reading_idx ON pico_reading(recording_time DESC);
