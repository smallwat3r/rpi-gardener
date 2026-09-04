-- No covering index: it would duplicate every row, doubling SD card writes per
-- insert. The chart, stats and latest queries only need the time index.
CREATE INDEX IF NOT EXISTS reading_idx ON reading(recording_time DESC);
