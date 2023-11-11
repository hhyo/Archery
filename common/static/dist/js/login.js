$(function () {
    $.ajaxSetup({
        headers: {"X-CSRFToken": getCookie("csrftoken")}
    });
});

function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = jQuery.trim(cookies[i]);
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

<!-- 退出登录后清空sessionStorage -->
$(document).ready(function () {
    sessionStorage.clear();
});

//回车键提交表单登录
$(document).ready(function () {
    $(document).keydown(function (event) {
        //keycode==13为回车键
        if (event.keyCode === 13 && $("#sign-up").css("display") === 'none') {
            $('#btnLogin').addClass('disabled');
            $('#btnLogin').prop('disabled', true);
            let username = $('#inputUsername').val();
            let password = $('#inputPassword').val();
            authenticateUser(username, password);
        }
    });
});

$('#toggle-tran-btn').click(
    function () {
        $(this).hide();
        $('#login-method-dingding').hide()
        $('#login-method-oidc').hide()
    }
)

$('#btnLogin').click(function () {
    $('#btnLogin').addClass('disabled');
    $('#btnLogin').prop('disabled', true);
    username = $('#inputUsername').val();
    password = $('#inputPassword').val();
    authenticateUser(username, password);
});

$('#btnSign').click(function () {
    $('#btnSign').addClass('disabled');
    $('#btnSign').prop('disabled', true);
    $.ajax({
        type: "post",
        url: "/signup/",
        dataType: "json",
        data: {
            username: $("#username").val(),
            password: $("#password").val(),
            password2: $("#password2").val(),
            display: $("#display").val(),
            email: $("#email").val(),
        },
        complete: function () {
            $('#btnSign').removeClass('disabled');
            $('#btnSign').prop('disabled', false);
        },
        success: function (data) {
            if (data.status === 0) {
                $("#sign-up").modal('hide');
                alert('注册成功, 请输入密码登录!');
            } else {
                alert(data.msg);
            }
        },
        error: function (XMLHttpRequest, textStatus, errorThrown) {
            alert(errorThrown);
        }
    });
});

function authenticateUser(username, password) {
    $.ajax({
        type: "post",
        url: "/authenticate/",
        dataType: "json",
        data: {
            username: username,
            password: password
        },
        complete: function () {
            $('#btnLogin').removeClass('disabled');
            $('#btnLogin').prop('disabled', false);
        },
        success: function (data) {
            if (data.status === 0) {
                if (data.data) {
                    document.cookie = "sessionid=" + data.data
                    $(location).attr('href', '/login/2fa/');
                } else {
                    $(location).attr('href', '/index/');
                }
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