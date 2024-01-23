Chart.defaults.font.family = 'Varela Round';
Chart.defaults.font.size = 11;
Chart.defaults.plugins.legend.display = false;
Chart.overrides.line.spanGaps = true;
Chart.overrides.line.borderWidth = 1;
Chart.overrides.line.pointStyle = false;
const chartRepr = new Chart(document.getElementById('chart'), {
  type: 'line',
  data: {
    datasets: [{
      label: 'Temperature (c)',
      data: data,
      borderColor: '#AE0000',
      yAxisID: 'y',
      parsing: {yAxisKey: 'temperature', xAxisKey: 'epoch'}
    }, {
      label: 'Humidity (%)',
      data: data,
      borderColor: '#007D73',
      yAxisID: 'y1',
      parsing: {yAxisKey: 'humidity', xAxisKey: 'epoch'}
    }]
  },
  options: {
    animation: {duration: 0},
    scales: {x:  {type: 'time', time: {unit: 'second', displayFormats: {second: 'HH:mm'}}},
             y:  {type: 'linear', display: true, position: 'left'},
             y1: {type: 'linear', display: true, position: 'right'}},
    interaction: {intersect: false, mode: 'index'},
  }
});
