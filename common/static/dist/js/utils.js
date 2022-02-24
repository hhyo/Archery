var onLoadErrorCallback = function (status, jqXHR) {
    if (status === 403) {
        alert("权限错误，您没有权限查看该数据！");
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
})(django.jQuery);
