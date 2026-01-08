SELECT plant_id
     , moisture
     , epoch
     , recording_time
FROM (
    SELECT plant_id
         , moisture
         , recording_time * 1000 as 'epoch'
         , datetime(recording_time, 'unixepoch') as 'recording_time'
         , ROW_NUMBER() OVER (PARTITION BY plant_id ORDER BY recording_time DESC) as rn
    FROM pico_reading
)
WHERE rn = 1
