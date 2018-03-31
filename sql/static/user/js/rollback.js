$(document).ready(function () {
    var isRollback = window.location.pathname.indexOf("rollback");
    if (isRollback != -1) {
        $("#btnSubmitRollback").click(function () {
            $(this).button('loading').delay(2500).queue(function () {
                $(this).button('reset');
                $(this).dequeue();
            });
            var editWorkflowNname = $("#editWorkflowNname").val();
            var editSqlContent = $("#editSqlContent").val();
            var editClustername = $("#editClustername").val();
            var editIsbackup = $("#editIsbackup").val();
            var editReviewman = $("#editReviewman").val();
            var editSubReviewman = $("#editSubReviewman").val();
            sessionStorage.removeItem('editWorkflowDetailId');
            sessionStorage.setItem('editWorkflowNname', editWorkflowNname);
            sessionStorage.setItem('editSqlContent', editSqlContent);
            sessionStorage.setItem('editClustername', editClustername);
            sessionStorage.setItem('editIsbackup', editIsbackup);
            sessionStorage.setItem('editReviewman', editReviewman);
            sessionStorage.setItem('editSubReviewman', editSubReviewman);
        });
    }
    ;
});
