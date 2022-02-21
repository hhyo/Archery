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
