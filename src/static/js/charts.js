Chart.defaults.font.family = 'monospace';
Chart.defaults.font.size = 12;
for (const chart of charts) {
  this[chart.name] = new Chart(document.getElementById(chart.id), {
    type: 'line',
    data: {
      datasets: [{
        label: chart.label,
        data: data,
        pointStyle: false,
        borderWidth: 1,
        borderColor: chart.color
      }]
    },
    options: {
      animation: {duration: 0},
      parsing: {xAxisKey: 'epoch', yAxisKey: chart.name},
      scales: {x: {type: 'time', time: {unit: 'second', displayFormats: {second: 'HH:mm'}}}},
      interaction: {intersect: false, mode: 'index'},
      plugins: {
        annotation: {
          annotations: {
            max_threshold: {type: 'line', borderWidth: 1, yMin: chart.max, yMax: chart.max, borderColor: 'rgba(97, 0, 94, 0.7)'},
            min_threshold: {type: 'line', borderWidth: 1, yMin: chart.min, yMax: chart.min, borderColor: 'rgba(6, 121, 0, 0.7)'}
      }}}}
  });
}
