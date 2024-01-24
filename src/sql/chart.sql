SELECT temperature
     , humidity
     , unixepoch(recording_time) * 1000 as 'epoch'
FROM reading
WHERE recording_time >= ?
ORDER BY recording_time DESC
