/*
Template Name: Color Admin - Responsive Admin Dashboard Template build with Twitter Bootstrap 3.3.4
Version: 1.7.0
Author: Sean Ngu
Website: http://www.seantheme.com/color-admin-v1.7/admin/
*/

var green = '#00acac',
    red = '#ff5b57',
    blue = '#348fe2',
    purple = '#727cb6',
    orange = '#f59c1a',
    black = '#2d353c';

var renderSwitcher = function() {
    if ($('[data-render=switchery]').length !== 0) {
        $('[data-render=switchery]').each(function() {
            var themeColor = green;
            if ($(this).attr('data-theme')) {
                switch ($(this).attr('data-theme')) {
                    case 'red':
                        themeColor = red;
                        break;
                    case 'blue':
                        themeColor = blue;
                        break;
                    case 'purple':
                        themeColor = purple;
                        break;
                    case 'orange':
                        themeColor = orange;
                        break;
                    case 'black':
                        themeColor = black;
                        break;
                }
            }
            var option = {};
                option.color = themeColor;
                option.secondaryColor = ($(this).attr('data-secondary-color')) ? $(this).attr('data-secondary-color') : '#dfdfdf';
                option.className = ($(this).attr('data-classname')) ? $(this).attr('data-classname') : 'switchery';
                option.disabled = ($(this).attr('data-disabled')) ? true : false;
                option.disabledOpacity = ($(this).attr('data-disabled-opacity')) ? $(this).attr('data-disabled-opacity') : 0.5;
                option.speed = ($(this).attr('data-speed')) ? $(this).attr('data-speed') : '0.5s';
            var switchery = new Switchery(this, option);
        });
    }
};

var checkSwitcherState = function() {
    $('[data-click="check-switchery-state"]').live('click', function() {
        alert($('[data-id="switchery-state"]').prop('checked'));
    });
    $('[data-change="check-switchery-state-text"]').live('change', function() {
        $('[data-id="switchery-state-text"]').text($(this).prop('checked'));
    });
};

// var renderPowerRangeSlider = function() {
//     if ($('[data-render="powerange-slider"]').length !== 0) {
//         $('[data-render="powerange-slider"]').each(function() {
//             var option = {};
//                 option.decimal = ($(this).attr('data-decimal')) ? $(this).attr('data-decimal') : false;
//                 option.disable = ($(this).attr('data-disable')) ? $(this).attr('data-disable') : false;
//                 option.disableOpacity = ($(this).attr('data-disable-opacity')) ? $(this).attr('data-disable-opacity') : 0.5;
//                 option.hideRange = ($(this).attr('data-hide-range')) ? $(this).attr('data-hide-range') : false;
//                 option.klass = ($(this).attr('data-class')) ? $(this).attr('data-class') : '';
//                 option.min = ($(this).attr('data-min')) ? $(this).attr('data-min') : 0;
//                 option.max = ($(this).attr('data-max')) ? $(this).attr('data-max') : 100;
//                 option.start = ($(this).attr('data-start')) ? $(this).attr('data-start') : null;
//                 option.step = ($(this).attr('data-step')) ? $(this).attr('data-step') : null;
//                 option.vertical = ($(this).attr('data-vertical')) ? $(this).attr('data-vertical') : false;
//             if ($(this).attr('data-height')) {
//                 $(this).closest('.slider-wrapper').height($(this).attr('data-height'));
//             }
//             var switchery = new Switchery(this, option);
//             var powerange = new Powerange(this, option);
//         });
//     }
// };

// var FormSliderSwitcher = function () {
// 	"use strict";
//     return {
//         //main function
//         init: function () {
//             $.getScript('assets/plugins/switchery/switchery.min.js').done(function() {
//                 // switchery
//                 renderSwitcher();
//                 checkSwitcherState();
//             });
            
//             $.getScript('assets/plugins/powerange/powerange.min.js').done(function() {
//                 // powerange slider
//                 renderPowerRangeSlider();
//             });
//         }
//     };
// }();