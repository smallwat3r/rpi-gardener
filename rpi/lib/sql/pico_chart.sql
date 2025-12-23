SELECT unixepoch(recording_time) * 1000 as 'epoch'
     , MAX(CASE WHEN plant_id = 'plant-1' THEN moisture END) as 'plant-1'
     , MAX(CASE WHEN plant_id = 'plant-2' THEN moisture END) as 'plant-2'
     , MAX(CASE WHEN plant_id = 'plant-3' THEN moisture END) as 'plant-3'
FROM pico_reading
WHERE recording_time >= ?
GROUP BY epoch
ORDER BY epoch DESC
