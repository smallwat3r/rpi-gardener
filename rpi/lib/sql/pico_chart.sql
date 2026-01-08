SELECT epoch
     , json_group_object(plant_id, moisture) as plants
FROM (
    SELECT (recording_time / :bucket * :bucket) * 1000 as epoch
         , CAST(plant_id AS TEXT) as plant_id
         , ROUND(AVG(moisture), 1) as moisture
    FROM pico_reading
    WHERE recording_time >= :from_epoch
    GROUP BY recording_time / :bucket, plant_id
)
GROUP BY epoch
ORDER BY epoch DESC
