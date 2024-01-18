Chart.defaults.font.family = 'Varela Round';
Chart.defaults.font.size = 11;
Chart.defaults.plugins.legend.display = false;
const charts = [
  {"name": "temperature", "color": "red", "id": "temperatureChart"},
  {"name": "humidity", "color": "blue", "id": "humidityChart"}
];
for (const chart of charts) {
  this[chart.name] = new Chart(document.getElementById(chart.id), {
    type: 'line',
    data: {datasets: [{
      data: data,
      pointStyle: false,
      borderWidth: 1,
      borderColor: chart.color
    }]},
    options: {
      animation: {duration: 0},
      parsing: {xAxisKey: 'epoch', yAxisKey: chart.name},
      scales: {x: {type: 'time', time: {unit: 'second', displayFormats: {second: 'HH:mm'}}}},
      interaction: {intersect: false, mode: 'index'},
    }
  });
}
