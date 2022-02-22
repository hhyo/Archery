var onLoadErrorCallback = function (status, jqXHR) {
    if (status === 403) {
        alert("权限错误，您没有权限查看该数据！");
    } else {
        alert("未知错误，请联系管理员处理！");
    }
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
