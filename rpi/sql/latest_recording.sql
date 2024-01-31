SELECT temperature
     , humidity
     , unixepoch(recording_time) * 1000 as 'epoch'
     , strftime('%Y-%m-%d %H:%M:%S', recording_time) as 'recording_time'
FROM reading
ORDER BY recording_time DESC
LIMIT 1
