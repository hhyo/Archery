$('#btnSync').click(function(){
	syncUser();
});

function syncUser() {
    $.ajax({
        type: "post",
        url: "/syncldapuser/",
        dataType: "json",
        data: {},
        complete: function () {
        },
        success: function (data) {
			$('#wrongpwd-modal-body').html(data.msg);
			$('#wrongpwd-modal').modal({
				keyboard: true
			});
		},
		error: function (XMLHttpRequest, textStatus, errorThrown) {
			alert(errorThrown);
        }
    });
};