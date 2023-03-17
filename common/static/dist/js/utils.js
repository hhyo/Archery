var onLoadErrorCallback = function (status, jqXHR) {
    if (status === 403) {
        alert("权限错误，您没有权限查看该数据！");
    } else if (jqXHR.statusText === "abort" || jqXHR.statusText === "canceled"){
        return 0
    } else {
        alert("未知错误，请联系管理员处理！");
    }
};

var dateFormat = function(fmt, date) {
    var o = {
        "M+": date.getMonth() + 1,                   //月份
        "d+": date.getDate(),                        //日
        "h+": date.getHours(),                       //小时
        "m+": date.getMinutes(),                     //分
        "s+": date.getSeconds(),                     //秒
        "q+": Math.floor((date.getMonth() + 3) / 3), //季度
        "S": date.getMilliseconds()                  //毫秒
    };
    if(/(y+)/.test(fmt))
        fmt = fmt.replace(RegExp.$1, (date.getFullYear() + "").substr(4 - RegExp.$1.length));
    for(var k in o)
        if(new RegExp("(" + k + ")").test(fmt))
            fmt = fmt.replace(RegExp.$1, (RegExp.$1.length == 1) ? (o[k]) : (("00" + o[k]).substr(("" + o[k]).length)));
    return fmt;
};

// 格式与高亮json格式的字符串
var jsonHighLight = function(json) {
    json = json.toString().replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
        var cls = 'text-muted';
        if (/^"/.test(match)) {
            if (/:$/.test(match)) {
                cls = 'text-success';
            } else {
                match = match
                cls = 'text-primary';
            }
        } else if (/true|false/.test(match)) {
            cls = 'text-success';
        } else if (/null/.test(match)) {
            cls = 'text-warning';
        }
        return '<span class="' + cls + '">' + match + '</span>';
    });
};

// 实例配置页面根据db_type选择显示或隐藏mode字段，mode字段只适用于redis实例
(function($) {
    $(function() {
        let db_type = $('#id_db_type');
        let mode = $('#id_mode').parent().parent();

        function toggleMode(value) {
            value === 'redis' ? mode.show() : mode.hide();
        }

        toggleMode(db_type.val());

        db_type.change(function() {
            toggleMode($(this).val());
        });
    });
})(jQuery);

// 短信验证码倒计时
let countdown = 60, clock, btn_captcha;
function init_countdown(obj) {
    btn_captcha = obj;
    btn_captcha.disabled = true;
    btn_captcha.innerText = countdown + ' 秒后重试';
    clock = setInterval(countdown_loop, 1000);
}

function countdown_loop() {
    countdown--;
    if(countdown > 0){
        btn_captcha.innerText = countdown + ' 秒后重试';
    } else {
        clearInterval(clock);
        btn_captcha.disabled = false;
        btn_captcha.innerText = '获取验证码';
        countdown = 60;
    }
}
