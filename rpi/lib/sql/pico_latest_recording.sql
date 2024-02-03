SELECT plant_id
     , moisture
     , unixepoch(max(recording_time)) * 1000 as 'epoch'
     , strftime('%Y-%m-%d %H:%M:%S', max(recording_time)) as 'recording_time'
FROM pico_reading
GROUP BY plant_id
