var monthChart = null; 		// 定义全局变量,月工单数量
var personChart = null; 	// 定义全局变量,个人工单数量

$(document).ready(function() {
  monthChart = new Highcharts.Chart({
    chart: {
      renderTo: 'container-month',
      type: 'spline',
      events: {
        load: getMonthWork // 图表加载完毕后执行的回调函数
      }
    },
    title: {
      text: '近三个月内工单数量'
    },
    xAxis: {
    },
    yAxis: {
      minPadding: 0.2,
      maxPadding: 0.2,
      title: {
        text: '工单数量',
        margin: 80
      }
    },
    series: [{
	  name: '日期（当日无工单则不显示）',
      data: []
    }]
  });

  personChart = new Highcharts.Chart({
    chart: {
      renderTo: 'container-engineer',
      type: 'column',
      events: {
        load: getPersonWork // 图表加载完毕后执行的回调函数
      }
    },
    title: {
      text: '近三个月内个人工单数量龙虎榜TOP 50'
    },
    xAxis: {
    },
    yAxis: {
      minPadding: 0.2,
      maxPadding: 0.2,
      title: {
        text: '工单数量',
        margin: 80
      }
    },
    series: [{
	  name: '工程师',
      data: []
    }]
  });
});

function getMonthWork() {
	$.ajax({
		type: 'get',
    	url: '/getMonthCharts/',
    	success: function(data) {
      		var series = monthChart.series[0],
        	shift = series.data.length > 1000; // 当数据点数量超过 20 个，则指定删除第一个点

      		// 新增点操作
      		//具体的参数详见：https://api.hcharts.cn/highcharts#Series.addPoint

			var category = new Array();
      		for(var i=0; i<data.length; i++){
				monthChart.series[0].addPoint([data[i][0],data[i][1]], true, shift);
				category.push(data[i][0]);
			}
			monthChart.xAxis[0].setCategories(category);
	  		// 一秒后继续调用本函数
	  		// setTimeout(getMonthWork, 1000);
		},
		cache: false,
		error: function(XMLHttpRequest, textStatus, errorThrown) {
            alert(errorThrown);
        }
    });
}


function getPersonWork() {
	$.ajax({
		type: 'get',
    	url: '/getPersonCharts/',
    	success: function(data) {
      		var series = personChart.series[0],
        	shift = series.data.length > 1000; // 当数据点数量超过 20 个，则指定删除第一个点

      		// 新增点操作
      		//具体的参数详见：https://api.hcharts.cn/highcharts#Series.addPoint

			var category = new Array();
      		for(var i=0; i<data.length; i++){
				personChart.series[0].addPoint([data[i][0],data[i][1]], true, shift);
				category.push(data[i][0]);
			}
			personChart.xAxis[0].setCategories(category);
	  		// 一秒后继续调用本函数
	  		// setTimeout(getMonthWork, 1000);
		},
		cache: false,
		error: function(XMLHttpRequest, textStatus, errorThrown) {
            alert(errorThrown);
        }
    });
}
