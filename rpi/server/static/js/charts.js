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
    scales: {x:  {type: 'time', ticks: {stepSize: 2}, time: {unit: 'second', displayFormats: {second: 'HH:mm'}}},
             y:  {type: 'linear', display: true, position: 'left', suggestedMin: 20, suggestedMax: 30},
             y1: {type: 'linear', display: true, position: 'right', suggestedMin: 40, suggestedMax: 65}},
    interaction: {intersect: false, mode: 'index'},
  }
});
const picoChartRepr = new Chart(document.getElementById('picoChart'), {
  type: 'line',
  data: {
    datasets: [{
      label: '1 Moisture (%)',
      data: picoData,
      borderColor: '#0949B7',
      yAxisID: 'y',
      parsing: {yAxisKey: 'plant-1', xAxisKey: 'epoch'}
    }, {
      label: '2 Moisture (%)',
      data: picoData,
      borderColor: '#194D33',
      yAxisID: 'y',
      parsing: {yAxisKey: 'plant-2', xAxisKey: 'epoch'}
    }, {
    }, {
      label: '3 Moisture (%)',
      data: picoData,
      borderColor: '#B76609',
      yAxisID: 'y',
      parsing: {yAxisKey: 'plant-3', xAxisKey: 'epoch'}
    }]
  },
  options: {
    animation: {duration: 0},
    scales: {x: {type: 'time', ticks: {stepSize: 2}, time: {unit: 'second', displayFormats: {second: 'HH:mm'}}},
             y: {type: 'linear', display: true, suggestedMin: 10, suggestedMax: 90}},
    interaction: {intersect: false, mode: 'index'},
  }
});
