$(document).ready(function () {
    $("#table_info").parent().hide();
    var handleDatepicker = function () {
        $('#datepicker-default').datepicker({
            todayHighlight: true
        });
        $('#datepicker-inline').datepicker({
            todayHighlight: true
        });
        $('.input-daterange').datepicker({
            todayHighlight: true
        });
        $('#datepicker-disabled-past').datepicker({
            todayHighlight: true
        });
        $('#datepicker-autoClose').datepicker({
            todayHighlight: true,
            autoclose: true
        });
    };
    handleDatepicker();
    renderSwitcher();
    $(".to_oracle").show();
    $(".to_mysql").hide();
    $(".to_oracle").parent().parent().show();
    $("#pubIp").change(function () {
        //获取数据库
        $.ajax({
            type: "post",
            url: "/instance/instance_resource/",
            dataType: "json",
            data: {
                instance_name: $("#pubIp").val(),
                resource_type: "database"
            },
            complete: function () {
            },
            success: function (data) {
                if (data.status === 0) {
                    var result = data.data;
                    $("#objname").empty();
                    for (var i = 0; i < result.length; i++) {
                        var name = "<option value=\"" + result[i] + "\">" + result[i] + "</option>";
                        $("#objname").append(name);
                    }
                    $("#objname").prepend("<option value=\"is-empty\" disabled=\"\" selected=\"selected\">请选择审核对象:</option>");
                } else {
                    alert(data.msg);
                }
            },
            error: function (XMLHttpRequest, textStatus, errorThrown) {
                alert(errorThrown);
            }
        });
    });
    $("input[name='optionstask']").click(function () {
        var rule_type = $("input[name='optionstask']:checked").val();
        var instance_name = $("#pubIp").val();
        if (!instance_name) {
            $("input[name='optionstask']:checked").prop("checked", false);
            return
        }
        $(".to_oracle").parent().parent().show();
        var flag = ""
        if (rule_type === "sqlplan") {
            flag = "sqlplan"
        } else if (rule_type === "text") {
            flag = "text";
        } else if (rule_type === "obj") {
            flag = "obj"
            $(".to_oracle").parent().parent().hide();
            $(".to_mysql").parent().parent().hide();
        } else if (rule_type === "sqlstat") {
            flag = "sqlstat"
        }
        $(".to_oracle").hide();
        $(".to_mysql").show();
        $.get("/themis/new/version/sql/review/get/struct", {
            'flag': flag,
            'instance_name': instance_name
        }, function (result) {
            if (result["errcode"] === 80050) {
                var columns = [
                    {"title": "规则名称"},
                    {"title": "规则概要"},
                    {
                        "title": "规则状态",
                        "fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
                            $(nTd).addClass('selectTd').attr('name', oData.rule_name + '_' + sData);
                        }
                    },
                    {
                        "title": "权重",
                        "fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
                            $(nTd).addClass('inputWeigth').attr('name', oData.rule_name + '_' + sData);
                        }
                    },
                    {
                        "title": "最高分",
                        "fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
                            $(nTd).addClass('inputMax').attr('name', oData.rule_name + '_' + sData);
                        }
                    },
                    {"title": "规则类型"},
                    //  "fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
                    //   $(nTd).addClass('inputMax').attr('name', oData.rule_name + '_' + sData);
                    // }
                    {"title": "db type"},
                    {"title": "exclude_type"}
                ]
                genTable("table_info", "struct_table", result["data"], columns);
                $("#table_info").parent().show();
            }
        });
    })
    $("#task_execute").click(function () {
        var data = {
            "instance_name": $("#pubIp").val(),
            "db_name": $("#objname").val(),
            "start_date": $("input[name='start']").val(),
            "stop_date": $("input[name='stop']").val(),
            "rule_type": $("input[name='optionstask']:checked").val()
        };
        $.post("/themis/new/version/sql/review/task/publish", data, function (result) {
            if (result["errcode"] === 80058) {
                alert(result["message"])
            }
            else {
                print_message("alert_message", "alert-danger", result["message"]);
            }
        });
    })
})

function genTable(domid, table_id, data, columns) {
    $("#" + domid).empty();
    $("#" + domid).append('<table class=\"table table-striped table-bordered\" id=\"' + table_id + '\"></table>')
    var table = $("#" + table_id).dataTable({
        "data": data,
        // "columns": columns    
        "columns": columns,
        "fnDrawCallback": function (data, x) {
            $('#' + table_id + ' tbody td.inputMax').editable('/new/version/sql/review/rule/info');
            $('#' + table_id + ' tbody td.selectTd').editable('/new/version/sql/review/rule/info', {
                data: {
                    "ON": "ON",
                    "OFF": "OFF"
                }, type: 'select', submit: 'OK'
            });
            // $('#' + table_id + ' tbody td.inputType').editable('/new/version/sql/review/rule/info');
        }
    });
    return table;
}
