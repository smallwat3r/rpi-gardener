SELECT plant_id
     , moisture
     , unixepoch(recording_time) * 1000 as 'epoch'
FROM pico_reading
WHERE recording_time >= ?
ORDER BY recording_time DESC
