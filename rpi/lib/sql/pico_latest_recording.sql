SELECT plant_id
     , moisture
     , recording_time * 1000 as 'epoch'
     , datetime(recording_time, 'unixepoch') as 'recording_time'
FROM pico_reading
WHERE recording_time = (SELECT MAX(recording_time) FROM pico_reading)
