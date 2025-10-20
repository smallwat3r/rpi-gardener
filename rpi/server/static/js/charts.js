Chart.defaults.font.family = 'Varela Round';
Chart.defaults.font.size = 11;
Chart.defaults.plugins.legend.display = false;
Chart.overrides.line.spanGaps = true;
Chart.overrides.line.borderWidth = 2;
Chart.overrides.line.pointStyle = false;
Chart.overrides.line.tension = 0.4;

const chartRepr = new Chart(document.getElementById('chart'), {
  type: 'line',
  data: {
    datasets: [{
      label: 'Temperature (c)',
      data: data,
      borderColor: '#ff5f00',
      yAxisID: 'y',
      parsing: {yAxisKey: 'temperature', xAxisKey: 'epoch'},
      shadowOffsetX: 2,
      shadowOffsetY: 2,
      shadowBlur: 5,
      shadowColor: 'rgba(255, 95, 0, 0.5)',
    }, {
      label: 'Humidity (%)',
      data: data,
      borderColor: '#00ffff',
      yAxisID: 'y1',
      parsing: {yAxisKey: 'humidity', xAxisKey: 'epoch'},
      shadowOffsetX: 2,
      shadowOffsetY: 2,
      shadowBlur: 5,
      shadowColor: 'rgba(0, 255, 255, 0.5)',
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: {duration: 0},
    scales: {x:  {type: 'time', ticks: {stepSize: 2}, time: {unit: 'second', displayFormats: {second: 'HH:mm'}}},
             y:  {type: 'linear', display: true, position: 'left', suggestedMin: 20, suggestedMax: 30},
             y1: {type: 'linear', display: true, position: 'right', suggestedMin: 40, suggestedMax: 65}},
    interaction: {intersect: false, mode: 'index'},
  }
});
const plantColors = ['#39ff14', '#ff00ff', '#bc13fe'];
let picoDataset = [];
for (let index in picoLatestInit) {
  let plantId = picoLatestInit[index]['plant_id'];
  picoDataset.push({
    label: `${plantId} %`,
    data: picoData,
    borderColor: plantColors[index],
    parsing: {yAxisKey: plantId, xAxisKey: 'epoch'},
    shadowOffsetX: 2,
    shadowOffsetY: 2,
    shadowBlur: 5,
    shadowColor: `${plantColors[index]}80`,  // add alpha for shadow
  });
};
const picoChartRepr = new Chart(document.getElementById('picoChart'), {
  type: 'line',
  data: {datasets: picoDataset},
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: {duration: 0},
    scales: {x: {type: 'time', ticks: {stepSize: 2}, time: {unit: 'second', displayFormats: {second: 'HH:mm'}}},
             y: {type: 'linear', display: true, suggestedMin: 10, suggestedMax: 90, min: 0}},
    interaction: {intersect: false, mode: 'index'},
    plugins: {
      legend: {
        display: false
      }
    }
  }
});
