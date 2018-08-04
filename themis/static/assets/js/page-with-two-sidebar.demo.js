/*
Template Name: Color Admin - Responsive Admin Dashboard Template build with Twitter Bootstrap 3.3.4
Version: 1.7.0
Author: Sean Ngu
Website: http://www.seantheme.com/color-admin-v1.7/admin/
*/

var getRandomValue = function() {
    var value = [];
    for (var i = 0; i<= 19; i++) {
        value.push(Math.floor((Math.random() * 10) + 1));
    }
    return value;
};

var handleRenderKnobDonutChart = function() {
    $('.knob').knob();
};

var handleRenderSparkline = function() {
    var blue		= '#348fe2',
        green		= '#00acac',
        purple		= '#727cb6',
        red         = '#ff5b57';
        
    var options = {
        height: '50px',
        width: '100%',
        fillColor: 'transparent',
        type: 'bar',
        barWidth: 8,
        barColor: green
    };
    
    var value = getRandomValue();
    $('#sidebar-sparkline-1').sparkline(value, options);
    
    value = getRandomValue();
    options.barColor = blue;
    $('#sidebar-sparkline-2').sparkline(value, options);
    
    value = getRandomValue();
    options.barColor = purple;
    $('#sidebar-sparkline-3').sparkline(value, options);
    
    value = getRandomValue();
    options.barColor = red;
    $('#sidebar-sparkline-4').sparkline(value, options);
};

var PageWithTwoSidebar = function () {
	"use strict";
    return {
        //main function
        init: function () {
            handleRenderKnobDonutChart();
            handleRenderSparkline();
        }
    };
}();