/*
Template Name: Color Admin - Responsive Admin Dashboard Template build with Twitter Bootstrap 3.3.4
Version: 1.7.0
Author: Sean Ngu
Website: http://www.seantheme.com/color-admin-v1.7/admin/
*/

var handleBootstrapWizards = function() {
	"use strict";
	$("#wizard").bwizard();
};

var FormWizard = function () {
	"use strict";
    return {
        //main function
        init: function () {
            $.getScript('assets/plugins/bootstrap-wizard/js/bwizard.js').done(function() {
                handleBootstrapWizards();
            });
        }
    };
}();