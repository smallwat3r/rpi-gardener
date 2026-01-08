SELECT temperature
     , humidity
     , recording_time * 1000 as 'epoch'
     , datetime(recording_time, 'unixepoch') as 'recording_time'
FROM reading
ORDER BY recording_time DESC
LIMIT 1
