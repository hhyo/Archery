var onLoadErrorCallback = function (status, jqXHR) {
    if (status === 403) {
        alert("权限错误，您没有权限查看该数据！");
    } else {
        alert("未知错误，数据加载失败！请检查接口返回信息和错误日志！");
    }
};
