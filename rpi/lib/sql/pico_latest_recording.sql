SELECT plant_id
     , moisture
     , epoch
     , recording_time
FROM (
    SELECT plant_id
         , moisture
         , unixepoch(recording_time) * 1000 as 'epoch'
         , strftime('%Y-%m-%d %H:%M:%S', recording_time) as 'recording_time'
         , ROW_NUMBER() OVER (PARTITION BY plant_id ORDER BY recording_time DESC) as rn
    FROM pico_reading
)
WHERE rn = 1
