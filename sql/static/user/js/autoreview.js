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


$("#btn-autoreview").click(function () {
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
        complete: function () {
            $('input[type=button]').removeClass('disabled');
            $('input[type=button]').addClass('btn');
            $('input[type=button]').prop('disabled', false);
        },
        success: function (data) {
            if (data.status === 0) {
                var result = data.data;
                //初始化表结构显示
                // 异步获取要动态生成的列
                var columns = [];
                $.each(result['column_list'], function (i, column) {
                    columns.push({"field": i, "title": column, "sortable": true});
                });
                $("#inception-result").bootstrapTable('destroy').bootstrapTable({
                        data: result['rows'],
                        columns: [{
                            title: 'ID',
                            field: 'ID',
                            sortable: true
                        }, {
                            title: 'SQL语句',
                            field: 'SQL',
                            formatter: function (value, row, index) {
                                var sql = value.replace(/\n/g, '<br>').replace(/\s/g, '&nbsp;');
                                if (value.length > 50) {
                                    return sql.substr(0, 50) + '...';
                                }
                                else {
                                    return sql
                                }
                            }
                        }, {
                            title: '扫描/影响行数',
                            field: 'Affected_rows',
                            sortable: true
                        }, {
                            title: '审核状态',
                            field: 'errlevel',
                            sortable: true,
                            formatter: function (value, row, index) {
                                if (value === 0) {
                                    return 'pass'
                                }
                                else if (value === 1) {
                                    return 'warning'
                                }
                                else if (value === 2) {
                                    return 'error'
                                }
                            }
                        }, {
                            title: '审核信息',
                            field: 'errormessage',
                            formatter: function (value, row, index) {
                                return value.replace(/\n/g, '<br>');
                            }
                        }],
                        rowStyle: function (row, index) {
                            var style = "";
                            if (row.errlevel === 1) {
                                style = 'warning';
                            }
                            else if (row.errlevel === 2) {
                                style = 'danger';
                            }
                            return {classes: style}
                        },
                        striped: true,                      //是否显示行间隔色
                        cache: false,                       //是否使用缓存，默认为true，所以一般情况下需要设置一下这个属性（*）
                        sortable: true,                     //是否启用排序
                        //sortOrder: "desc",                   //排序方式
                        //sortName: 'errormessage',           //排序字段
                        pagination: true,                   //是否显示分页（*）
                        sidePagination: "client",           //分页方式：client客户端分页，server服务端分页（*）
                        pageNumber: 1,                      //初始化加载第一页，默认第一页,并记录
                        pageSize: 30,                     //每页的记录行数（*）
                        pageList: [30, 50, 100],       //可供选择的每页的行数（*）
                        search: false,                      //是否显示表格搜索
                        strictSearch: false,                //是否全匹配搜索
                        showColumns: true,                  //是否显示所有的列（选择显示的列）
                        showRefresh: false,                  //是否显示刷新按钮
                        showExport: true,
                        exportDataType: "all",
                        minimumCountColumns: 2,             //最少允许的列数
                        uniqueId: "ID",                     //每一行的唯一标识，一般为主键列
                        showToggle: true,                   //是否显示详细视图和列表视图的切换按钮
                        cardView: false,                    //是否显示详细视图
                        detailView: true,                  //是否显示父子表
                        //格式化详情
                        detailFormatter: function (index, row) {
                            var html = [];
                            $.each(row, function (key, value) {
                                if (key === 'SQL') {
                                    var sql = value;
                                    //替换所有的换行符
                                    sql = sql.replace(/\r\n/g, "<br>");
                                    sql = sql.replace(/\n/g, "<br>");
                                    //替换所有的空格
                                    sql = sql.replace(/\s/g, "&nbsp;");
                                    html.push('<span>' + sql + '</span>');
                                }
                            });
                            return html.join('');
                        }
                    }
                );
                //记录审核结果
                sessionStorage.setItem('CheckWarningCount', result['CheckWarningCount']);
                sessionStorage.setItem('CheckErrorCount', result['CheckErrorCount']);
                $("#inception-result").show();
            } else {
                alert("status: " + data.status + "\nmsg: " + data.msg + data.data);
            }
        },
        error: function (XMLHttpRequest, textStatus, errorThrown) {
            alert(errorThrown);
        }
    });

}
