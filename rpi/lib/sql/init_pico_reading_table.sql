CREATE TABLE IF NOT EXISTS pico_reading(
    id INTEGER PRIMARY KEY,
    plant_id INTEGER NOT NULL,
    moisture REAL NOT NULL,
    recording_time TEXT NOT NULL
)
