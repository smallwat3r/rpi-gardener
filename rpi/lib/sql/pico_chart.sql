SELECT (recording_time / :bucket * :bucket) * 1000 as epoch
     , plant_id
     , ROUND(AVG(moisture), 1) as moisture
FROM pico_reading
WHERE recording_time >= :from_epoch
GROUP BY recording_time / :bucket, plant_id
ORDER BY epoch DESC
