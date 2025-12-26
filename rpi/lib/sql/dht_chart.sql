SELECT ROUND(AVG(temperature), 1) as temperature
     , ROUND(AVG(humidity), 1) as humidity
     , (unixepoch(recording_time) / :bucket * :bucket) * 1000 as epoch
FROM reading
WHERE recording_time >= :from_time
GROUP BY unixepoch(recording_time) / :bucket
ORDER BY epoch DESC
