Chart.defaults.font.family = 'Varela Round';
Chart.defaults.font.size = 11;
Chart.defaults.borderColor = 'rgba(216, 216, 216, 0.2)';
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
      borderColor: 'rgba(217, 0, 97, 0.8)',
      yAxisID: 'y',
      parsing: {yAxisKey: 'temperature', xAxisKey: 'epoch'}
    }, {
      label: 'Humidity (%)',
      data: data,
      borderColor: 'rgba(0, 102, 255, 0.8)',
      yAxisID: 'y1',
      parsing: {yAxisKey: 'humidity', xAxisKey: 'epoch'}
    }]
  },
  options: {
    animation: {duration: 0},
    scales: {x:  {type: 'time', ticks: {stepSize: 2},
                  time: {unit: 'second', displayFormats: {second: 'HH:mm'}}},
             y:  {type: 'linear', display: true,
                  title: {display: true, text: 'Temperature (c)', color: 'rgba(217, 0, 97, 0.8)'}, grid: {color: 'rgba(216, 216, 216, 0.2)'},
                  position: 'left', suggestedMin: 20, suggestedMax: 30},
             y1: {type: 'linear', display: true,
                  title: {display: true, text: 'Humidity (%)', color: 'rgba(0, 102, 255, 0.8)'},
                  position: 'right', suggestedMin: 40, suggestedMax: 65,
                  grid: {drawOnChartArea: false}}},
    interaction: {intersect: false, mode: 'index'},
  }
});
