/*
Template Name: Color Admin - Responsive Admin Dashboard Template build with Twitter Bootstrap 3.3.4
Version: 1.7.0
Author: Sean Ngu
Website: http://www.seantheme.com/color-admin-v1.7/admin/
*/

var handleDataTableResponsive = function() {
	"use strict";
    
    if ($('#data-table').length !== 0) {
        $('#data-table').DataTable({
            responsive: true
        });
    }
};

var TableManageResponsive = function () {
	"use strict";
    return {
        //main function
        init: function () {
            $.getScript('assets/plugins/DataTables/js/jquery.dataTables.js').done(function() {
                $.getScript('assets/plugins/DataTables/js/dataTables.responsive.js').done(function() {
                    handleDataTableResponsive();
                });
            });
        }
    };
}();