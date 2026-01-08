SELECT p.plant_id
     , p.moisture
     , p.recording_time * 1000 as 'epoch'
     , datetime(p.recording_time, 'unixepoch') as 'recording_time'
FROM pico_reading p
INNER JOIN (
    SELECT plant_id, MAX(recording_time) as max_time
    FROM pico_reading
    GROUP BY plant_id
) latest ON p.plant_id = latest.plant_id AND p.recording_time = latest.max_time
