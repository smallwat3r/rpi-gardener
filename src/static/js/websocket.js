const latest = new WebSocket(`ws://${location.host}/latest`);
const activeCharts = [temperature, humidity];
let lastEpoch = null;
latest.onmessage = function(message) {
  let data = JSON.parse(message.data);
  if (data.epoch === lastEpoch) return;
  cTemperature.textContent = data.temperature;
  cHumidity.textContent = data.humidity;
  cRecordingTime.textContent = data.recording_time;
  for (const chart of activeCharts) {
    chart.data.datasets[0].data.pop();
    chart.data.datasets[0].data.unshift(data);
    chart.update();
  }
  lastEpoch = data.epoch;
}
const average = new WebSocket(`ws://${location.host}/average`);
average.onmessage = function(message) {
  let data = JSON.parse(message.data);
  aTemperature.textContent = data.temperature;
  aHumidity.textContent = data.humidity;
  console.log(data)
}
