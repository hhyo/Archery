/*
Template Name: Color Admin - Responsive Admin Dashboard Template build with Twitter Bootstrap 3.3.4
Version: 1.7.0
Author: Sean Ngu
Website: http://www.seantheme.com/color-admin-v1.7/admin/
*/

var handleEmailActionButtonStatus = function() {
    if ($('[data-checked=email-checkbox]:checked').length !== 0) {
        $('[data-email-action]').removeClass('hide');
    } else {
        $('[data-email-action]').addClass('hide');
    }
};

var handleEmailCheckboxChecked = function() {
    $('[data-checked=email-checkbox]').live('click', function() {
        var targetLabel = $(this).closest('label');
        var targetEmailList = $(this).closest('li');
        if ($(this).prop('checked')) {
            $(targetLabel).addClass('active');
            $(targetEmailList).addClass('selected');
        } else {
            $(targetLabel).removeClass('active');
            $(targetEmailList).removeClass('selected');
        }
        handleEmailActionButtonStatus();
    });
};

var handleEmailAction = function() {
    $('[data-email-action]').live('click', function() {
        var targetEmailList = '[data-checked=email-checkbox]:checked';
        if ($(targetEmailList).length !== 0) {
            $(targetEmailList).closest('li').slideToggle(function() {
                $(this).remove();
                handleEmailActionButtonStatus();
            });
        }
    });
};

var InboxV2 = function () {
	"use strict";
    return {
        //main function
        init: function () {
            handleEmailCheckboxChecked();
            handleEmailAction();
        }
    };
}();