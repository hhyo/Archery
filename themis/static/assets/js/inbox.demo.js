/*
Template Name: Color Admin - Responsive Admin Dashboard Template build with Twitter Bootstrap 3.3.4
Version: 1.7.0
Author: Sean Ngu
Website: http://www.seantheme.com/color-admin-v1.7/admin/
*/

var handleSelectAll = function () {
	"use strict";
    $('[data-click=email-select-all]').live('click', function(e) {
        e.preventDefault();
        if ($(this).closest('tr').hasClass('active')) {
            $('.table-email tr').removeClass('active');
        } else {
            $('.table-email tr').addClass('active');
        }
    });
};

var handleSelectSingle = function () {
	"use strict";
    $('[data-click=email-select-single]').live('click', function(e) { 
        e.preventDefault();
        var targetRow = $(this).closest('tr');
        if ($(targetRow).hasClass('active')) {
            $(targetRow).removeClass('active');
        } else {
            $(targetRow).addClass('active');
        }
    });
};

var handleEmailRemove = function () {
	"use strict";
    $('[data-click=email-remove]').live('click', function(e) { 
        e.preventDefault();
        var targetRow = $(this).closest('tr');
        $(targetRow).fadeOut().remove();
    });
};

var handleEmailHighlight = function () {
	"use strict";
    $('[data-click=email-highlight]').live('click', function(e) { 
        e.preventDefault();
        if ($(this).hasClass('text-danger')) {
            $(this).removeClass('text-danger');
        } else {
            $(this).addClass('text-danger');
        }
    });
};

var Inbox = function () {
	"use strict";
    return {
        //main function
        init: function () {
            handleSelectAll();
            handleSelectSingle();
            handleEmailRemove();
            handleEmailHighlight();
        }
    };
}();