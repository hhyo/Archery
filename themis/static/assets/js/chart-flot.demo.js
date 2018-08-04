/*
Template Name: Color Admin - Responsive Admin Dashboard Template build with Twitter Bootstrap 3.3.4
Version: 1.7.0
Author: Sean Ngu
Website: http://www.seantheme.com/color-admin-v1.7/admin/
*/

var blue		= '#348fe2',
    blueLight	= '#5da5e8',
    blueDark	= '#1993E4',
    aqua		= '#49b6d6',
    aquaLight	= '#6dc5de',
    aquaDark	= '#3a92ab',
	green		= '#00acac',
	greenLight	= '#33bdbd',
	greenDark	= '#008a8a',
	orange		= '#f59c1a',
	orangeLight	= '#f7b048',
	orangeDark	= '#c47d15',
    dark		= '#2d353c',
    grey		= '#b6c2c9',
    purple		= '#727cb6',
    purpleLight	= '#8e96c5',
    purpleDark	= '#5b6392',
    red         = '#ff5b57';
    
var handleBasicChart = function () {
	"use strict";
	var d1 = [];
	for (var x = 0; x < Math.PI * 2; x += 0.25) {
		d1.push([x, Math.sin(x)]);
	}
	var d2 = [];
	for (var y = 0; y < Math.PI * 2; y += 0.25) {
		d2.push([y, Math.cos(y)]);
	}
	var d3 = [];
	for (var z = 0; z < Math.PI * 2; z += 0.1) {
		d3.push([z, Math.tan(z)]);
	}
	if ($('#basic-chart').length !== 0) {
        $.plot($("#basic-chart"), [
            { label: "data 1",  data: d1, color: purple, shadowSize: 0 },
            { label: "data 2",  data: d2, color: green, shadowSize: 0 },
            { label: "data 3",  data: d3, color: dark, shadowSize: 0 }
        ], {
            series: {
                lines: { show: true },
                points: { show: false }
            },
            xaxis: {
                tickColor: '#ddd'
            },
            yaxis: {
                min: -2,
                max: 2,
                tickColor: '#ddd'
            },
            grid: {
                borderColor: '#ddd',
                borderWidth: 1
            }
        });
	}
};
var handleStackedChart = function () {
	"use strict";
	var d1 = [];
    for (var a = 0; a <= 5; a += 1) {
        d1.push([a, parseInt(Math.random() * 5)]);
    }
    var d2 = [];
    for (var b = 0; b <= 5; b += 1) {
        d2.push([b, parseInt(Math.random() * 5 + 5)]);
    }
    var d3 = [];
    for (var c = 0; c <= 5; c += 1) {
        d3.push([c, parseInt(Math.random() * 5 + 5)]);
    }
    var d4 = [];
    for (var d = 0; d <= 5; d += 1) {
        d4.push([d, parseInt(Math.random() * 5 + 5)]);
    }
    var d5 = [];
    for (var e = 0; e <= 5; e += 1) {
        d5.push([e, parseInt(Math.random() * 5 + 5)]);
    }
    var d6 = [];
    for (var f = 0; f <= 5; f += 1) {
        d6.push([f, parseInt(Math.random() * 5 + 5)]);
    }
    var ticksLabel = [
        [0, "Monday"], [1, "Tuesday"], [2, "Wednesday"], [3, "Thursday"],
        [4, "Friday"], [5, "Saturday"]
    ];
    
    var options = { 
        xaxis: {  tickColor: 'transparent',  ticks: ticksLabel},
        yaxis: {  tickColor: '#ddd', ticksLength: 10},
        grid: { 
            hoverable: true, 
            tickColor: "#ccc",
            borderWidth: 0,
            borderColor: 'rgba(0,0,0,0.2)'
        },
        series: {
            stack: true,
            lines: { show: false, fill: false, steps: false },
            bars: { show: true, barWidth: 0.5, align: 'center', fillColor: null },
            highlightColor: 'rgba(0,0,0,0.8)'
        },
        legend: {
            show: true,
            labelBoxBorderColor: '#ccc',
            position: 'ne',
            noColumns: 1
        }
    };
    var xData = [
        {
            data:d1,
            color: purpleDark,
            label: 'China',
            bars: {
                fillColor: purpleDark
            }
        },
        {
            data:d2,
            color: purple,
            label: 'Russia',
            bars: {
                fillColor: purple
            }
        },
        {
            data:d3,
            color: purpleLight,
            label: 'Canada',
            bars: {
                fillColor: purpleLight
            }
        },
        {
            data:d4,
            color: blueDark,
            label: 'Japan',
            bars: {
                fillColor: blueDark
            }
        },
        {
            data:d5,
            color: blue,
            label: 'USA',
            bars: {
                fillColor: blue
            }
        },
        {
            data:d6,
            color: blueLight,
            label: 'Others',
            bars: {
                fillColor: blueLight
            }
        }
    ];
    $.plot("#stacked-chart", xData, options);
    
    function showTooltip2(x, y, contents) {
        $('<div id="tooltip" class="flot-tooltip">' + contents + '</div>').css( {
            top: y,
            left: x + 35
        }).appendTo("body").fadeIn(200);
    }
    var previousXValue = null;
    var previousYValue = null;
    $("#stacked-chart").bind("plothover", function (event, pos, item) {
        if (item) {
            var y = item.datapoint[1] - item.datapoint[2];
            
            if (previousXValue != item.series.label || y != previousYValue) {
                previousXValue = item.series.label;
                previousYValue = y;
                $("#tooltip").remove();
    
                showTooltip2(item.pageX, item.pageY, y + " " + item.series.label);
            }
        }
        else {
            $("#tooltip").remove();
            previousXValue = null;
            previousYValue = null;       
        }
    });
};
var handleTrackingChart = function () {
	"use strict";
	var sin = [], cos = [];
	for (var i = 0; i < 14; i += 0.1) {
		sin.push([i, Math.sin(i)]);
		cos.push([i, Math.cos(i)]);
	}
    
        
    function updateLegend() {
        updateLegendTimeout = null;
        
        var pos = latestPosition;
        
        var axes = plot.getAxes();
        if (pos.x < axes.xaxis.min || pos.x > axes.xaxis.max ||
            pos.y < axes.yaxis.min || pos.y > axes.yaxis.max) {
            return;
        }
        var i, j, dataset = plot.getData();
        for (i = 0; i < dataset.length; ++i) {
            var series = dataset[i];

            for (j = 0; j < series.data.length; ++j) {
                if (series.data[j][0] > pos.x) {
                    break;
                }
            }
            
            var y, p1 = series.data[j - 1], p2 = series.data[j];
            if (p1 === null) {
                y = p2[1];
            } else if (p2 === null) {
                y = p1[1];
            } else {
                y = p1[1] + (p2[1] - p1[1]) * (pos.x - p1[0]) / (p2[0] - p1[0]);
            }

            legends.eq(i).text(series.label.replace(/=.*/, "= " + y.toFixed(2)));
        }
    }
	if ($('#tracking-chart').length !== 0) {
        var plot = $.plot($("#tracking-chart"),
        [ 
            { data: sin, label: "Series1", color: dark, shadowSize: 0},
            { data: cos, label: "Series2", color: red, shadowSize: 0} 
        ], 
        {
            series: {
                lines: { show: true }
            },
            crosshair: { mode: "x", color: grey },
            grid: { hoverable: true, autoHighlight: false, borderColor: '#ccc', borderWidth: 0 },
            xaxis: {  tickLength: 0 },
            yaxis: {  tickColor: '#ddd' },
            legend: {
                labelBoxBorderColor: '#ddd',
                backgroundOpacity: 0.4,
                color:'#fff',
                show: true
            }
        });
        var legends = $("#tracking-chart .legendLabel");
        legends.each(function () {
            $(this).css('width', $(this).width());
        });
    
        var updateLegendTimeout = null;
        var latestPosition = null;
        
        $("#tracking-chart").bind("plothover",  function (pos) {
            latestPosition = pos;
            if (!updateLegendTimeout) {
                updateLegendTimeout = setTimeout(updateLegend, 50);
            }
        });
	}
};
var handleBarChart = function () {
	"use strict";
	if ($('#bar-chart').length !== 0) {
        var data = [ ["January", 10], ["February", 8], ["March", 4], ["April", 13], ["May", 17], ["June", 9] ];
        $.plot("#bar-chart", [ {data: data, color: purple} ], {
            series: {
                bars: {
                    show: true,
                    barWidth: 0.4,
                    align: 'center',
                    fill: true,
                    fillColor: purple,
                    zero: true
                }
            },
            xaxis: {
                mode: "categories",
                tickColor: '#ddd',
				tickLength: 0
            },
            grid: {
                borderWidth: 0
            }
        });
    }
};
var handleInteractivePieChart = function () {
	"use strict";
	if ($('#interactive-pie-chart').length !== 0) {
        var data = [];
        var series = 3;
        var colorArray = [purple, dark, grey];
        for( var i = 0; i<series; i++)
        {
            data[i] = { label: "Series"+(i+1), data: Math.floor(Math.random()*100)+1, color: colorArray[i]};
        }
        $.plot($("#interactive-pie-chart"), data,
        {
            series: {
                pie: { 
                    show: true
                }
            },
            grid: {
                hoverable: true,
                clickable: true
            },
            legend: {
                labelBoxBorderColor: '#ddd',
                backgroundColor: 'none'
            }
        });
    }
};
var handleDonutChart = function () {
	"use strict";
	if ($('#donut-chart').length !== 0) {
        var data = [];
        var series = 3;
        var colorArray = [dark, green, purple];
        var nameArray = ['Unique Visitor', 'Bounce Rate', 'Total Page Views', 'Avg Time On Site', '% New Visits'];
        var dataArray = [20,14,12,31,23];
        for( var i = 0; i<series; i++)
        {
            data[i] = { label: nameArray[i], data: dataArray[i], color: colorArray[i] };
        }
        
        $.plot($("#donut-chart"), data, 
        {
            series: {
                pie: { 
                    innerRadius: 0.5,
                    show: true,
                    combine: {
                        color: '#999',
                        threshold: 0.1
                    }
                }
            },
            grid:{borderWidth:0, hoverable: true, clickable: true},
            legend: {
                show: false
            }
        });
    }
};
var handleInteractiveChart = function () {
	"use strict";
    function showTooltip(x, y, contents) {
        $('<div id="tooltip" class="flot-tooltip">' + contents + '</div>').css( {
            top: y - 45,
            left: x - 55
        }).appendTo("body").fadeIn(200);
    }
	if ($('#interactive-chart').length !== 0) {
        var d1 = [[0, 42], [1, 53], [2,66], [3, 60], [4, 68], [5, 66], [6,71],[7, 75], [8, 69], [9,70], [10, 68], [11, 72], [12, 78], [13, 86]];
        var d2 = [[0, 12], [1, 26], [2,13], [3, 18], [4, 35], [5, 23], [6, 18],[7, 35], [8, 24], [9,14], [10, 14], [11, 29], [12, 30], [13, 43]];
        
        $.plot($("#interactive-chart"), [
                {
                    data: d1, 
                    label: "Page Views", 
                    color: purple,
                    lines: { show: true, fill:false, lineWidth: 2 },
                    points: { show: false, radius: 5, fillColor: '#fff' },
                    shadowSize: 0
                }, {
                    data: d2,
                    label: 'Visitors',
                    color: green,
                    lines: { show: true, fill:false, lineWidth: 2, fillColor: '' },
                    points: { show: false, radius: 3, fillColor: '#fff' },
                    shadowSize: 0
                }
            ], 
            {
                xaxis: {  tickColor: '#ddd',tickSize: 2 },
                yaxis: {  tickColor: '#ddd', tickSize: 20 },
                grid: { 
                    hoverable: true, 
                    clickable: true,
                    tickColor: "#ccc",
                    borderWidth: 1,
                    borderColor: '#ddd'
                },
                legend: {
                    labelBoxBorderColor: '#ddd',
                    margin: 0,
                    noColumns: 1,
                    show: true
                }
            }
        );
        var previousPoint = null;
        $("#interactive-chart").bind("plothover", function (event, pos, item) {
            $("#x").text(pos.x.toFixed(2));
            $("#y").text(pos.y.toFixed(2));
            if (item) {
                if (previousPoint !== item.dataIndex) {
                    previousPoint = item.dataIndex;
                    $("#tooltip").remove();
                    var y = item.datapoint[1].toFixed(2);
                    
                    var content = item.series.label + " " + y;
                    showTooltip(item.pageX, item.pageY, content);
                }
            } else {
                $("#tooltip").remove();
                previousPoint = null;            
            }
            event.preventDefault();
        });
    }
};
var handleLiveUpdatedChart = function () {
	"use strict";
        
    function update() {
        plot.setData([ getRandomData() ]);
        // since the axes don't change, we don't need to call plot.setupGrid()
        plot.draw();
        
        setTimeout(update, updateInterval);
    }
    function getRandomData() {
        if (data.length > 0) {
            data = data.slice(1);
        }

        // do a random walk
        while (data.length < totalPoints) {
            var prev = data.length > 0 ? data[data.length - 1] : 50;
            var y = prev + Math.random() * 10 - 5;
            if (y < 0) {
                y = 0;
            }
            if (y > 100) {
                y = 100;
            }
            data.push(y);
        }

        // zip the generated y values with the x values
        var res = [];
        for (var i = 0; i < data.length; ++i) {
            res.push([i, data[i]]);
        }
        return res;
    }
	if ($('#live-updated-chart').length !== 0) {
        var data = [], totalPoints = 150;
        
        // setup control widget
        var updateInterval = 1000;
        $("#updateInterval").val(updateInterval).change(function () {
            var v = $(this).val();
            if (v && !isNaN(+v)) {
                updateInterval = +v;
                if (updateInterval < 1) {
                    updateInterval = 1;
                }
                if (updateInterval > 2000) {
                    updateInterval = 2000;
                }
                $(this).val("" + updateInterval);
            }
        });
        
        // setup plot
        var options = {
            series: { shadowSize: 0, color: purple, lines: { show: true, fill:true } }, // drawing is faster without shadows
            yaxis: { min: 0, max: 100, tickColor: '#ddd' },
            xaxis: { show: true, tickColor: '#ddd' },
            grid: {
                borderWidth: 1,
                borderColor: '#ddd'
            }
        };
        var plot = $.plot($("#live-updated-chart"), [ getRandomData() ], options);
        
        update();
    }
};


var Chart = function () {
	"use strict";
    return {
        //main function
        init: function () {
            $.getScript('assets/plugins/flot/jquery.flot.min.js').done(function() {
                $.getScript('assets/plugins/flot/jquery.flot.time.min.js').done(function() {
                    $.getScript('assets/plugins/flot/jquery.flot.resize.min.js').done(function() {
                        $.getScript('assets/plugins/flot/jquery.flot.pie.min.js').done(function() {
                            $.getScript('assets/plugins/flot/jquery.flot.stack.min.js').done(function() {
                                $.getScript('assets/plugins/flot/jquery.flot.crosshair.min.js').done(function() {
                                    $.getScript('assets/plugins/flot/jquery.flot.categories.js').done(function() {
                                        handleBasicChart();
                                        handleStackedChart();
                                        handleTrackingChart();
                                        handleBarChart();
                                        handleInteractivePieChart();
                                        handleDonutChart();
                                        handleInteractiveChart();
                                        handleLiveUpdatedChart();
                                    });
                                });
                            });
                        });
                    });
                });
            });
        }
    };
}();