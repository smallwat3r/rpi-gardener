SELECT temperature
     , humidity
     , unixepoch(recording_time) * 1000 as 'epoch'
FROM reading
ORDER BY recording_time DESC
LIMIT 5000
