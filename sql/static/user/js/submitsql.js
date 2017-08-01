function validateForm(element) {
	var result = true;
	element.find('[required]').each(
		function () {
			var fieldElement = $(this);
			//如果为null则设置为''
			var value = fieldElement.val() || '';
			if (value) {
				value = value.trim();
			}
			if (!value || value === fieldElement.attr('data-placeholder')) {
				alert((fieldElement.attr('data-name') || this.name) + "不能为空！");
				result = false;
				return result;
			}
		}
	);
	return result;
}

$("#btn-submitsql").click(function (){
	//获取form对象，判断输入，通过则提交
	var formSubmit = $("#form-submitsql");

	if (validateForm(formSubmit)) {
		formSubmit.submit();
	}
});

$("#review_man").change(function review_man(){
    var review_man = $(this).val();
    $("div#" + review_man).hide();
});

$(document).ready(function () {
	var pathname = window.location.pathname;
	if (pathname == "/editsql/") {
		document.getElementById('workflowid').value = sessionStorage.getItem('editWorkflowDetailId');
		document.getElementById('workflow_name').value = sessionStorage.getItem('editWorkflowNname');
		document.getElementById('sql_content').value = sessionStorage.getItem('editSqlContent');
		document.getElementById('cluster_name').value = sessionStorage.getItem('editClustername');
		document.getElementById('is_backup').value = sessionStorage.getItem('editIsbackup');
		document.getElementById('review_man').value = sessionStorage.getItem('editReviewman');
		var sub_review_name = sessionStorage.getItem('editSubReviewman');
		$("input[name='sub_review_man'][value=\'"+sub_review_name+"\']").attr("checked", true);
	}
});