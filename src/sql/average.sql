SELECT round(avg(temperature), 2) as 'temperature'
     , round(avg(humidity), 2) as 'humidity'
FROM reading
WHERE recording_time > ?
