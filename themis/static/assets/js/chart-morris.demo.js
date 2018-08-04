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
    
var handleMorrisLineChart = function () {
    var tax_data = [
        {"period": "2011 Q3", "licensed": 3407, "sorned": 660},
        {"period": "2011 Q2", "licensed": 3351, "sorned": 629},
        {"period": "2011 Q1", "licensed": 3269, "sorned": 618},
        {"period": "2010 Q4", "licensed": 3246, "sorned": 661},
        {"period": "2009 Q4", "licensed": 3171, "sorned": 676},
        {"period": "2008 Q4", "licensed": 3155, "sorned": 681},
        {"period": "2007 Q4", "licensed": 3226, "sorned": 620},
        {"period": "2006 Q4", "licensed": 3245, "sorned": null},
        {"period": "2005 Q4", "licensed": 3289, "sorned": null}
    ];
    Morris.Line({
        element: 'morris-line-chart',
        data: tax_data,
        xkey: 'period',
        ykeys: ['licensed', 'sorned'],
        labels: ['Licensed', 'Off the road'],
        resize: true,
        lineColors: [dark, blue]
    });
};
    
var handleMorrisBarChart = function () {
    Morris.Bar({
        element: 'morris-bar-chart',
        data: [
            {device: 'iPhone', geekbench: 136},
            {device: 'iPhone 3G', geekbench: 137},
            {device: 'iPhone 3GS', geekbench: 275},
            {device: 'iPhone 4', geekbench: 380},
            {device: 'iPhone 4S', geekbench: 655},
            {device: 'iPhone 5', geekbench: 1571}
        ],
        xkey: 'device',
        ykeys: ['geekbench'],
        labels: ['Geekbench'],
        barRatio: 0.4,
        xLabelAngle: 35,
        hideHover: 'auto',
        resize: true,
        barColors: [dark]
    });
};

var handleMorrisAreaChart = function() {
    Morris.Area({
        element: 'morris-area-chart',
        data: [
            {period: '2010 Q1', iphone: 2666, ipad: null, itouch: 2647},
            {period: '2010 Q2', iphone: 2778, ipad: 2294, itouch: 2441},
            {period: '2010 Q3', iphone: 4912, ipad: 1969, itouch: 2501},
            {period: '2010 Q4', iphone: 3767, ipad: 3597, itouch: 5689},
            {period: '2011 Q1', iphone: 6810, ipad: 1914, itouch: 2293},
            {period: '2011 Q2', iphone: 5670, ipad: 4293, itouch: 1881},
            {period: '2011 Q3', iphone: 4820, ipad: 3795, itouch: 1588},
            {period: '2011 Q4', iphone: 15073, ipad: 5967, itouch: 5175},
            {period: '2012 Q1', iphone: 10687, ipad: 4460, itouch: 2028},
            {period: '2012 Q2', iphone: 8432, ipad: 5713, itouch: 1791}
        ],
        xkey: 'period',
        ykeys: ['iphone', 'ipad', 'itouch'],
        labels: ['iPhone', 'iPad', 'iPod Touch'],
        pointSize: 2,
        hideHover: 'auto',
        resize: true,
        lineColors: [red, orange, dark]
    });
};

var handleMorrisDonusChart = function() {
    Morris.Donut({
        element: 'morris-donut-chart',
        data: [
            {label: 'Jam', value: 25 },
            {label: 'Frosted', value: 40 },
            {label: 'Custard', value: 25 },
            {label: 'Sugar', value: 10 }
        ],
        formatter: function (y) { return y + "%" },
        resize: true,
        colors: [dark, orange, red, grey]
    });
};


var MorrisChart = function () {
	"use strict";
    return {
        //main function
        init: function () {
            $.getScript('assets/plugins/morris/raphael.min.js').done(function() {
                $.getScript('assets/plugins/morris/morris.js').done(function() {
                    handleMorrisLineChart();
                    handleMorrisBarChart();
                    handleMorrisAreaChart();
                    handleMorrisDonusChart();
                });
            });
        }
    };
}();