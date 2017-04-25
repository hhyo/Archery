//回车键提交表单登录
$(document).ready(function() {
	$(document).keydown(function(event) {
		//keycode==13为回车键
		if (event.keyCode == 13) {
			authenticateUser();
		}
	});
});

$('#btnLogin').click(function(){
	authenticateUser();
});

function authenticateUser() {
	var inputUsername = $('#inputUsername');
	var inputPassword = $('#inputPassword');
    $.ajax({
        type: "post",
        url: "/authenticate/",
        dataType: "json",
        data: {
			username: inputUsername.val(),
            password: inputPassword.val()
        },
        complete: function () {
        },
        success: function (data) {
			if (data.status == 0) {
				$(location).attr('href','/allworkflow/');
			} else {
				$('#wrongpwd-modal-body').html(data.msg);
				$('#wrongpwd-modal').modal({
        			keyboard: true
    			});
			}
		},
		error: function (XMLHttpRequest, textStatus, errorThrown) {
			alert(errorThrown);
        }
    });
};
