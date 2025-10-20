Chart.defaults.font.family = 'Inter';
Chart.defaults.color = '#f8f9fa';
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
      borderColor: '#ff00ff',
      yAxisID: 'y',
      parsing: {yAxisKey: 'temperature', xAxisKey: 'epoch'},
    }, {
      label: 'Humidity (%)',
      data: data,
      borderColor: '#00ffff',
      yAxisID: 'y1',
      parsing: {yAxisKey: 'humidity', xAxisKey: 'epoch'},
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: {duration: 0},
    scales: {
      x:  {
        type: 'time',
        ticks: {stepSize: 2, color: '#f8f9fa'},
        time: {
          unit: 'second',
          displayFormats: {second: 'HH:mm'},
          tooltipFormat: 'yyyy-MM-dd HH:mm'
        },
        grid: {color: '#495057'}
      },
      y:  {
        type: 'linear',
        display: true,
        position: 'left',
        suggestedMin: 20,
        suggestedMax: 30,
        ticks: {color: '#f8f9fa'},
        grid: {color: '#495057'}
      },
      y1: {
        type: 'linear',
        display: true,
        position: 'right',
        suggestedMin: 40,
        suggestedMax: 65,
        ticks: {color: '#f8f9fa'},
        grid: {color: '#495057'}
      }
    },
    interaction: {intersect: false, mode: 'index'},
  }
});
const plantColors = ['#9d34a0', '#00aaff', '#ff00ff'];
let picoDataset = [];
for (let index in picoLatestInit) {
  let plantId = picoLatestInit[index]['plant_id'];
  picoDataset.push({
    label: `${plantId} %`,
    data: picoData,
    borderColor: plantColors[index],
    parsing: {yAxisKey: plantId, xAxisKey: 'epoch'},
  });
};
const picoChartRepr = new Chart(document.getElementById('picoChart'), {
  type: 'line',
  data: {datasets: picoDataset},
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: {duration: 0},
    scales: {
      x: {
        type: 'time',
        ticks: {stepSize: 2, color: '#f8f9fa'},
        time: {
          unit: 'second',
          displayFormats: {second: 'HH:mm'},
          tooltipFormat: 'yyyy-MM-dd HH:mm'
        },
        grid: {color: '#495057'}
      },
      y: {
        type: 'linear',
        display: true,
        suggestedMin: 10,
        suggestedMax: 90,
        min: 0,
        ticks: {color: '#f8f9fa'},
        grid: {color: '#495057'}
      }
    },
    interaction: {intersect: false, mode: 'index'},
    plugins: {
      legend: {
        display: false
      }
    }
  }
});
