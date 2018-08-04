/*
Template Name: Color Admin - Responsive Admin Dashboard Template build with Twitter Bootstrap 3.3.4
Version: 1.7.0
Author: Sean Ngu
Website: http://www.seantheme.com/color-admin-v1.7/admin/
*/

var handleDataTableKeyTable = function() {
	"use strict";
    
    if ($('#data-table').length !== 0) {
        var table = $('#data-table').DataTable({
            scrollY: 320,
            paging: false,
            "autoWidth": true
        });

        new $.fn.dataTable.KeyTable(table);
    }
};

var TableManageKeyTable = function () {
	"use strict";
    return {
        //main function
        init: function () {
            $.getScript('assets/plugins/DataTables/js/jquery.dataTables.js').done(function() {
                $.getScript('assets/plugins/DataTables/js/dataTables.keyTable.js').done(function() {
                    handleDataTableKeyTable();
                });
            });
        }
    };
}();