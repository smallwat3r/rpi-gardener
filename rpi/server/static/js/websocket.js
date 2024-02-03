const dhtLatest = new WebSocket(`ws://${location.host}/dht/latest`);
let lastEpoch = null;
dhtLatest.onmessage = function(message) {
  let data = JSON.parse(message.data);
  if (data.epoch === lastEpoch) return;
  cTemperature.textContent = data.temperature;
  cHumidity.textContent = data.humidity;
  cRecordingTime.textContent = data.recording_time;
  for (let step = 0; step < 2; step++) {
    chartRepr.data.datasets[step].data.pop();
    chartRepr.data.datasets[step].data.unshift(data);
  }
  chartRepr.update();
  lastEpoch = data.epoch;
}
const dhtAverage = new WebSocket(`ws://${location.host}/dht/stats?hours=${hours}`);
dhtAverage.onmessage = function(message) {
  let data = JSON.parse(message.data);
  aTemperature.textContent = data.avg_temperature;
  minTemperature.textContent = data.min_temperature;
  maxTemperature.textContent = data.max_temperature;
  aHumidity.textContent = data.avg_humidity;
  minHumidity.textContent = data.min_humidity;
  maxHumidity.textContent = data.max_humidity;
}
const picoLatest = new WebSocket(`ws://${location.host}/pico/latest`);
let picoLastEpoch = null;
picoLatest.onmessage = function(message) {
  let data = JSON.parse(message.data);
  if (data[0].epoch === picoLastEpoch) return;
  picoRecordingTime.textContent = data[0].recording_time;
  for (let index in data) {
    document.getElementById(`moisture${data[index].plant_id}`).textContent =
      data[index].moisture;
    picoChartRepr.data.datasets[index].data.pop();
    let newData = {'epoch': data[index].epoch};
    newData[`${data[index].plant_id}`] = data[index].moisture;
    picoChartRepr.data.datasets[index].data.unshift(newData);
  }
  picoChartRepr.update();
  picoLastEpoch = data[0].epoch;
}
