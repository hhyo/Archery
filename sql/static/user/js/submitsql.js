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
	var sqlContent = editor.getValue();
	$("#sql_content").val(sqlContent);

	if (validateForm(formSubmit)) {
		formSubmit.submit();
	}
});

$("#btn-reset").click(function (){
	editor.setValue("");
	//重置选择器
	$(".selectpicker").selectpicker('val', '');
	$(".selectpicker").selectpicker('render');
	$(".selectpicker").selectpicker('refresh');
});

$("#review_man").change(function review_man(){
    var review_man = $(this).val();
    $("div#" + review_man).hide();
});

$(document).ready(function () {
	var pathname = window.location.pathname;
	if (pathname == "/editsql/") {
		editor.setValue("请在此提交SQL，请以分号结尾。例如：use test; create table t1(id int)engine=innodb;");
		editor.clearSelection();
		// 禁用提交按钮，点击检测后才激活
		$("#btn-submitsql").addClass('disabled');
		$("#btn-submitsql").prop('disabled', true);
		$("#workflowid").val(sessionStorage.getItem('editWorkflowDetailId'));
		$("#workflow_name").val(sessionStorage.getItem('editWorkflowNname'));
		editor.setValue(sessionStorage.getItem('editSqlContent'));
		editor.clearSelection();
		$("#cluster_name").val(sessionStorage.getItem('editClustername'));
		$("#is_backup").val(sessionStorage.getItem('editIsbackup'));
		$("#review_man").val(sessionStorage.getItem('editReviewman'));
		var sub_review_name = sessionStorage.getItem('editSubReviewman');
		$("input[name='sub_review_man'][value=\'"+sub_review_name+"\']").attr("checked", true);
	}
	else if (pathname === "/submitothercluster/") {
		editor.setValue("请在此提交SQL，请以分号结尾。例如：use test; create table t1(id int)engine=innodb;");
		editor.clearSelection();
		// 禁用提交按钮，点击检测后才激活
		$("#btn-submitsql").addClass('disabled');
		$("#btn-submitsql").prop('disabled', true);
		$("#workflow_name").val(sessionStorage.getItem('editWorkflowNname'));
		editor.setValue(sessionStorage.getItem('editSqlContent'));
		editor.clearSelection();
		$("#is_backup").val(sessionStorage.getItem('editIsbackup'));
		$("#review_man").val(sessionStorage.getItem('editReviewman'));
		var sub_review_name = sessionStorage.getItem('editSubReviewman');
		$("input[name='sub_review_man'][value=\'"+sub_review_name+"\']").attr("checked", true);
	}
	else if (pathname === "/submitsql/"){
		editor.setValue("请在此提交SQL，请以分号结尾。例如：use test; create table t1(id int)engine=innodb;");
		editor.clearSelection();
		// 禁用提交按钮，点击检测后才激活
		$("#btn-submitsql").addClass('disabled');
		$("#btn-submitsql").prop('disabled', true);
	}
});
