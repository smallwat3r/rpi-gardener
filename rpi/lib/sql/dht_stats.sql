SELECT round(avg(temperature), 2) as 'avg_temperature'
     , max(temperature) as 'max_temperature'
     , min(temperature) as 'min_temperature'
     , round(avg(humidity), 2) as 'avg_humidity'
     , max(humidity) as 'max_humidity'
     , min(humidity) as 'min_humidity'
FROM reading
WHERE recording_time > :from_epoch
