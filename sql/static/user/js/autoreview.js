function validate() {
	var result = true;
	var sqlContent = editor.getValue();
	var clusterName = $("#cluster_name").val();
	if (sqlContent === null || sqlContent.trim() === "" || sqlContent == $("#sql_content").attr("placeholder")) {
		alert("SQL内容不能为空！");
		return result = false;
	} else if (clusterName === null || clusterName == $("#cluster_name").attr("data-placeholder")) {
		alert("请选择要上线的集群！");
		return result = false;
	}
	return result;
}


$("#btn-autoreview").click(function(){
	//先做表单验证，成功了提交ajax给后端
	if (validate()) {
	    $('#btn-autoreview').addClass('disabled');
	    $('#btn-autoreview').prop('disabled', true);
		autoreview();
	}
	else {
	    $('#btn-autoreview').removeClass('disabled');
	    $('#btn-autoreview').addClass('btn');
	    $('#btn-autoreview').prop('disabled', false);
    }
});

function autoreview() {
	var sqlContent = editor.getValue();
	var clusterName = $("#cluster_name");

	//将数据通过ajax提交给后端进行检查
	$.ajax({
		type: "post",
		url: "/simplecheck/",
		dataType: "json",
		data: {
			sql_content: sqlContent,
			cluster_name: clusterName.val()
		},
		complete: function() {
		    $('input[type=button]').removeClass('disabled');
		    $('input[type=button]').addClass('btn');
		    $('input[type=button]').prop('disabled', false);
		},
		success: function (data) {
			if (data.status == 0) {
				//console.log(data.data);
				var result = data.data;
				var finalHtml = "<table class='table' width='100%' style='table-layout:fixed;'> " +
                            "<thead><tr><th width='50%'>SQL语句</th><th width='110px'>扫描/影响行数</th><th width='100px'>审核状态</th><th>审核信息</th></tr></thead>" +
                            "</table>";
				for (var i=0; i<result.length; i++) {
					//索引5是SQL，4是审核建议，2是审核结果
					var sql = result[i][5].replace(/\n/g,'<br>');
					var suggest = result[i][4].replace(/\n/g,'<br>');
					var affected_rows = result[i][6];
					var level = "pass";
					alertStyle = "alert-success";
					if (result[i][2] === 2) {
						alertStyle = "alert-danger";
						level = 'error';
					}
					else if (result[i][2] === 1) {
						alertStyle = "alert-warning";
						level = 'warning';
					}
					finalHtml += "<div class='alert alert-dismissable " + alertStyle + "'> " +
                                "<button type='button' class='close' data-dismiss='alert' aria-hidden='true'>x</button>" +
                                "<table class='' width='100%' style='table-layout:fixed;'> " +
                                "<tbody><tr>" +
                                "<td width='52%' style='word-wrap:break-word;'>" + sql + "</td>" +
                                "<td width='110px'>" + affected_rows + "</td>" +
                                "<td width='100px'>" + level + "</td>" +
                                "<td>" + suggest + "</td>" +
                                "</tr> </tbody></table> </div>";
				}

				$("#inception-result-col").html(finalHtml);
				//填充内容后展现出来
				$("#inception-result").show();
			} else {
				alert("status: " + data.status + "\nmsg: " + data.msg + data.data);
			}
		},
		error: function(XMLHttpRequest, textStatus, errorThrown) {
			alert(errorThrown);
		}
	});

}
