var oTable;
$(document).ready(function(){
    $.get("/new/version/sql/review/prevent/object", {}, function(result){
        if(result["errcode"] === 80052){
            var columns = [
                { "title": "用户"},
                { "title": "对象名称"},
                { "title": "对象类型"},
                { "title": "db类型"},
                { "title": "ip地址"},
                { "title": "实例名或端口"},
                {    
                    "title": "操作",
                    "fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
                    $(nTd).html("<input type='checkbox' name='rule_detail_list' value='" + sData + "'>");
                    }
                }
            
            ]
            oTable = $("#table_data").dataTable({
                "data": result["data"],
                "columns": columns,
                "sDom": "<'row'<'col-md-6 btnBox'><'col-md-6'f>r>t<'row-fluid'<'col-md-6'i><'col-md-6 'p>>",
                "language": {
                   "sProcessing": "处理中...",
                   "sLengthMenu": "显示 _MENU_ 项结果",
                   "sZeroRecords": "没有匹配结果",
                   "sInfo": "显示第 _START_ 至 _END_ 项结果，共 _TOTAL_ 项",
                   "sInfoEmpty": "显示第 0 至 0 项结果，共 0 项",
                   "sInfoFiltered": "(由 _MAX_ 项结果过滤)",
                   "sInfoPostFix": "",
                   "sSearch": "搜索:",
                   "sUrl": "",
                   "sEmptyTable": "表中数据为空",
                   "sLoadingRecords": "载入中...",
                   "sInfoThousands": ",",
                   "oPaginate": {
                       "sFirst": "首页",
                       "sPrevious": "上页",
                       "sNext": "下页",
                       "sLast": "末页"
                   }
                },
                "fnInitComplete": function (oSettings, json) {
                      $('<button class="btn btn-primary" id="cancel_prevent_obj">取消屏蔽</button> ' + '&nbsp;').appendTo($('.btnBox'));
                }
            });
        }
    });
    $body = $(document.body)
    $body.on("click", "#cancel_prevent_obj",  function(){
        var table_list = oTable.fnGetNodes();
        var json_list = [];
        for (var i = 0; i < table_list.length; i++){
            if($(table_list[i]).find("input").is(":checked")){
                var info = $(table_list[i]).find("td")
                var temp = {
                    "ipaddress": $(info[4]).text(),
                    "db_type": $(info[3]).text(),
                    "username": $(info[0]).text(),
                    "object_name": $(info[1]).text(),
                    "object_type": $(info[2]).text(),
                    "port_db_name": $(info[5]).text()
                }
                json_list.push(temp);
            }
        }
        var json_data = {
                "flag": 0,
                "json_list": json_list
        }
        json_data = JSON.stringify(json_data)
        $.post("/new/version/sql/review/prevent/object", json_data, function(result){
            if (result["errcode"] === 80053) {
                
            }
        })
    });
})