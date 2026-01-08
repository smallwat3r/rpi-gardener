SELECT (recording_time / :bucket * :bucket) * 1000 as epoch
     , json_group_object(CAST(plant_id AS TEXT), ROUND(AVG(moisture), 1)) as plants
FROM pico_reading
WHERE recording_time >= :from_epoch
GROUP BY recording_time / :bucket
ORDER BY epoch DESC
