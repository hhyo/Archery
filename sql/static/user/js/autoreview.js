function validate() {
	var result = true;
	var sqlContent = $("#sql_content").val();
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
		autoreview();
	}
});

function autoreview() {
	var sqlContent = $("#sql_content");
	var clusterName = $("#cluster_name");
	
	//将数据通过ajax提交给后端进行检查
	$.ajax({
		type: "post",
		url: "/simplecheck/",
		dataType: "json",
		data: {
			sql_content: sqlContent.val(),
			cluster_name: clusterName.val()
		},
		complete: function() {

		},
		success: function (data) {
			if (data.status == 0) {
				//console.log(data.data);
				var result = data.data;
				var finalHtml = "";
				for (var i=0; i<result.length; i++) {
					//索引5是SQL，4是审核建议
					var sql = result[i][5].replace(/\n/g,'<br>');
					var suggest = result[i][4].replace(/\n/g,'<br>');
					alertStyle = "alert-success";
					if (result[i][4] != "None") {
						alertStyle = "alert-danger";
					}
					finalHtml += "<div class='alert alert-dismissable " + alertStyle + "'> <button type='button' class='close' data-dismiss='alert' aria-hidden='true'>x</button> <table class=''> <tr> <td width='800px'>" + sql + "</td> <td><strong>自动审核结果：</strong>" + suggest + "</td> </tr> </table> </div>";
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
