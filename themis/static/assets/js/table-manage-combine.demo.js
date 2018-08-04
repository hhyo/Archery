/*
Template Name: Color Admin - Responsive Admin Dashboard Template build with Twitter Bootstrap 3.3.4
Version: 1.7.0
Author: Sean Ngu
Website: http://www.seantheme.com/color-admin-v1.7/admin/
*/

var handleDataTableCombinationSetting = function() {
	"use strict";
    
    if ($('#data-table').length !== 0) {
        if ($(window).width() >= 767) {
            var table = $('#data-table').DataTable({
                ajax:           "assets/plugins/DataTables/json/scroller-demo.json",
                dom: 'TRC<"clear">lfrtip',
                tableTools: {
                    "sSwfPath": "assets/plugins/DataTables/swf/copy_csv_xls_pdf.swf"
                },
                "lengthMenu": [20, 40, 60]
            });
            new $.fn.dataTable.FixedHeader(table);
            new $.fn.dataTable.KeyTable(table);
            new $.fn.dataTable.AutoFill(table, {
                mode: 'both',
                complete: function ( altered ) {
                    var last = altered[ altered.length-1 ];
    
                    $.gritter.add({
                        title: 'Table Column Updated <i class="fa fa-check-circle text-success m-l-3"></i>',
                        text: altered.length+' cells were altered in this auto-fill. The value of the last cell altered was: <span class="text-white">'+last.oldValue+'</span> and is now <span class="text-white">'+last.newValue+'</span>',
                        sticky: true,
                        time: '',
                        class_name: 'my-sticky-class'
                    });
                }
            });
        } else {
            var table = $('#data-table').DataTable({
                ajax:           "assets/plugins/DataTables/json/scroller-demo.json",
                dom: '<"clear">frtip',
                "lengthMenu": [20, 40, 60]
            });
        }
    }
};

var TableManageCombine = function () {
	"use strict";
    return {
        //main function
        init: function () {
            $.getScript('assets/plugins/DataTables/js/jquery.dataTables.js').done(function() {
                $.getScript('assets/plugins/DataTables/js/dataTables.autoFill.js').done(function() {
                    $.getScript('assets/plugins/DataTables/js/dataTables.colReorder.js').done(function() {
                        $.getScript('assets/plugins/DataTables/js/dataTables.colVis.js').done(function() {
                            $.getScript('assets/plugins/DataTables/js/dataTables.fixedHeader.js').done(function() {
                                $.getScript('assets/plugins/DataTables/js/dataTables.keyTable.js').done(function() {
                                    $.getScript('assets/plugins/DataTables/js/dataTables.tableTools.js').done(function() {
                                        $.getScript('assets/plugins/gritter/js/jquery.gritter.js').done(function() {
                                            handleDataTableCombinationSetting();
                                        });
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