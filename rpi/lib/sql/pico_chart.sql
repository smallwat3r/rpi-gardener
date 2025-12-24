SELECT unixepoch(recording_time) * 1000 as epoch
     , plant_id
     , moisture
FROM pico_reading
WHERE recording_time >= ?
ORDER BY epoch DESC
