var rule_detail_table;
$(document).ready(function(){
    var handleDatepicker = function() {
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
    oTable = $("#table_data").dataTable({
        "iDisplayLength":10,
        "serverSide": true,
        // "sAjaxSource": "/sensitive/get/data",
        "ajax": {
            "url": "/themis/new/version/sql/review/job/data",
            "type": "GET",
            "data": function(d){
              d.username = $("#username").val(),
              d.operuser = $("#operuser").val(),
              d.status = $("#status").val(),
              d.starttime = $("input[name='start']").val(),
              d.endtime = $("input[name='end']").val()
            }
        },
        'bPaginate': true,
        'searching': false,
        "bDestory": true,
        "bRetrieve": true,
        "bFilter":true,
        "bSort": false,
        // "bProcessing": true,
        "aoColumns": [
            {"mDataProp": "operuser"},
            {"mDataProp": "username"},
            {"mDataProp": "create_time"},
            {"mDataProp": "status"},
            {"mDataProp": "task_type"},
            {"mDataProp": "capture_start_time"},
            {"mDataProp": "capture_stop_time"},
            {
            "mDataProp": "id",
            "fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
                $(nTd).html("<input type='checkbox' name='check_list' value='" + sData + "'>");
                }
            },
        ],
        "sDom": "<'row'<'col-md-6 myBtnBox'><'col-md-6'f>r>t<'row-fluid'<'col-md-6'i><'col-md-6 'p>>",
        // "sPaginationType": "bootstrap",
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
              // $('<a class="btn btn-primary" id="export_report">导出报告</a> ' + '&nbsp;').appendTo($('.myBtnBox'));
              $('<button class="btn btn-primary" id="view_report">查看报告</button> ' + '&nbsp;').appendTo($('.myBtnBox'));
        }
       //  "fnCreatedRow": function(nRow, aData, iDataIndex) {
       //         $('td:eq(0)', nRow).html("<div class='class-ip'><span class='row-details row-details-close' data_id='" + aData["id"] + "'></span><span>" + aData["ipaddress"] + "</span></div>");
       //  }
    });
    $("#search_data").on("click", function(){
      oTable.fnReloadAjax();
      $("#base").empty()
      $("#rule_detail").empty();
      $("#text_detail").empty();
      $("#plan_detail").empty();
      $("#stat_detail").empty();
      $("#obj_detail").empty();
    });
    $body = $(document.body)
    $body.on("click", "#view_report",  function(){
      var item = $("input[name='check_list']:checked")
      if(item.length != 1) {
        alert("只能选择一条规则");
        return
      }else{
        var task_uuid = item.val()
        var rule_type = $($(item).parent().parent().find("td")[4]).text()
        $.post("/themis/new/version/sql/review/task/rule/info", {"flag": "1", "task_uuid": task_uuid, "rule_type": rule_type}, function(result){
          if (result["errcode"] === 80050){
            var pie_flag = 0
            $("#rule_detail").empty();
            $("#text_detail").empty();
            $("#plan_detail").empty();
            $("#stat_detail").empty();
            $("#obj_detail").empty();
            if (result["rule_flag"] === "OBJ"){
                  var columns = [
                    {
                      "title": "规则名称",
                      "fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
                          $(nTd).html("<a href='#rule_detail' class='task_rule_detail' task_uuid='" + result["task_uuid"] +"' value='" + sData + "' onclick='fn_rule_detail(this)'>" + sData + "</a>");
                          }
                    },
                    { "title": "规则描述"},
                    { "title": "违反次数"},
                    { "title": "扣分"}
                  ]
                  pie_flag = 3
            }else if(result["rule_flag"] === "SQLPLAN" || result["rule_flag"] === "SQLSTAT"){
              var columns = [
                    {
                      "title": "规则名称",
                      "fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
                          $(nTd).html("<a href='#rule_detail' class='task_rule_detail' task_uuid='" + result["task_uuid"] +"' value='" + sData + "' onclick='fn_rule_detail(this)'>" + sData + "</a>");
                          }
                    },
                    { "title": "规则描述"},
                    { "title": "违反次数"},
                    { "title": "扣分"}
                  ]
                pie_flag = 3;
            }else if(result["rule_flag"] === "TEXT"){
              var columns = [
                    {
                      "title": "规则名称",
                      "fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
                          $(nTd).html("<a href='#rule_detail' class='task_rule_detail' task_uuid='" + result["task_uuid"] +"' value='" + sData + "' onclick='fn_rule_detail(this)'>" + sData + "</a>");
                          }
                    },
                    { "title": "规则描述"},
                    { "title": "违反次数"},
                    { "title": "扣分"}
                  ]
                pie_flag = 3;
            }
              var title = result["ip"] + " " + result["port"] + " "+ result["schema"] + "规则概览"
              var legend = []
              var pie_data = []
              var deduct_marks = 0
              for(var i in result["rules"]){
                legend.push(result["rules"][i][0])
                pie_data.push({"value": result["rules"][i][pie_flag], "name": result["rules"][i][0]})
                deduct_marks += parseFloat(result["rules"][i][pie_flag])
              }
              var score =  (result["total_score"] - deduct_marks) / result["total_score"] * 100
              $("#base").empty()
              var chart_title = "规则总分: " + score.toFixed(3)
              genCharts(chart_title, "规则扣分详情", legend, pie_data)
              genTable("#base", title, "rule_info", result["rules"], columns)
          }
        })
      }
    });
    $body.on("click", "#export_report", function(result){
      var item = $("input[name='check_list']:checked")
      if(item.length != 1) {
        alert("只能选择一条规则");
        return
      }else{
        var task_uuid = item.val()
        var rule_type = $($(item).parent().parent().find("td")[4]).text()
      }
      data =  {"task_uuid": task_uuid, "rule_type": rule_type}
      $.get("/new/version/sql/review/task/rule/export", data, function(result){
        if(result["errcode"] === 80052){
          var hostname = window.location.hostname;
          alert("请用此连接下载: " + hostname + ":9000/download?filename=" + result["task_uuid"])
          return
        }
        else{
          alert(result["message"])
          return
        }
      })
    })
});

jQuery.fn.dataTableExt.oApi.fnReloadAjax = function ( oSettings, sNewSource, fnCallback, bStandingRedraw )
{
    // DataTables 1.10 compatibility - if 1.10 then `versionCheck` exists.
    // 1.10's API has ajax reloading built in, so we use those abilities
    // directly.
    if ( jQuery.fn.dataTable.versionCheck ) {
        var api = new jQuery.fn.dataTable.Api( oSettings );

        if ( sNewSource ) {
            api.ajax.url( sNewSource ).load( fnCallback, !bStandingRedraw );
        }
        else {
            api.ajax.reload( fnCallback, !bStandingRedraw );
        }
        return;
    }

    if ( sNewSource !== undefined && sNewSource !== null ) {
        oSettings.sAjaxSource = sNewSource;
    }

    // Server-side processing should just call fnDraw
    if ( oSettings.oFeatures.bServerSide ) {
        this.fnDraw();
        return;
    }

    this.oApi._fnProcessingDisplay( oSettings, true );
    var that = this;
    var iStart = oSettings._iDisplayStart;
    var aData = [];

    this.oApi._fnServerParams( oSettings, aData );

    oSettings.fnServerData.call( oSettings.oInstance, oSettings.sAjaxSource, aData, function(json) {
        /* Clear the old information from the table */
        that.oApi._fnClearTable( oSettings );

        /* Got the data - add it to the table */
        var aData =  (oSettings.sAjaxDataProp !== "") ?
            that.oApi._fnGetObjectDataFn( oSettings.sAjaxDataProp )( json ) : json;

        for ( var i=0 ; i<aData.length ; i++ )
        {
            that.oApi._fnAddData( oSettings, aData[i] );
        }

        oSettings.aiDisplay = oSettings.aiDisplayMaster.slice();

        that.fnDraw();

        if ( bStandingRedraw === true )
        {
            oSettings._iDisplayStart = iStart;
            that.oApi._fnCalculateEnd( oSettings );
            that.fnDraw( false );
        }

        that.oApi._fnProcessingDisplay( oSettings, false );

        /* Callback user function - for event handlers etc */
        if ( typeof fnCallback == 'function' && fnCallback !== null )
        {
            fnCallback( oSettings );
        }
    }, oSettings );
};
function genTable(domid, title, table_id, data, columns){
    // $("#base").append("<table class=\"table table-striped table-bordered\" id=\"" + table_id + "\"></table>\"")
    $(domid).append('<div class=\"panel panel-inverse\">\
                          <div class=\"panel-heading\">\
                              <h4 class=\"panel-title\">' + title + '</h4>\
                          </div>\
                          <div class=\"panel-body\">\
                              <div class=\"table-responsive\">\
                              <table class=\"table table-striped table-bordered table_rule\" id=\"' + table_id +'\"></table>\
                            </div>\
                          </div>\
                  </div>')
    var table = $("#" + table_id).dataTable({
        "data": data,
        "columns": columns,
        "order": [[ 3, "desc" ]],
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
    });
    return table;
}
function genTable_v2(domid, title, table_id, data, columns, solution, rule_name){
    // $("#base").append("<table class=\"table table-striped table-bordered\" id=\"" + table_id + "\"></table>\"")
    $(domid).append('<div class=\"panel panel-inverse\">\
                          <div class=\"panel-heading\">\
                              <h4 class=\"panel-title\">' + title + '</h4>\
                          </div>\
                          <div class=\"panel-body\">\
                          <button class=\"btn btn-primary m-r-5 m-b-5 accordion-toggle accordion-toggle-styled collapsed\" data-toggle=\"collapse\" href=\"#solution_' + rule_name + '\">解决方案</button>\
                            <div id=\"solution_' + rule_name + '\" class=\"panel panel-body panel-collapse collapse\">' + solution + '</div>\
                              <div class=\"table-responsive\">\
                              <table class=\"table table-striped table-bordered table_rule\" id=\"' + table_id +'\"></table>\
                            </div>\
                          </div>\
                  </div>')
    var table = $("#" + table_id).dataTable({
        "data": data,
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
        // "fnInitComplete": function (oSettings, json) {
        //       $('<button class="btn btn-primary" id="prevent_obj">屏蔽</button> ' + '&nbsp;').appendTo($('.btnBox'));
        // }

    });
    return table;
}

function genTable_v3(domid, title, table_id, data, columns){
    // $("#base").append("<table class=\"table table-striped table-bordered\" id=\"" + table_id + "\"></table>\"")
    $(domid).append('<div class=\"panel panel-inverse\">\
                          <div class=\"panel-heading\">\
                              <h4 class=\"panel-title\">' + title + '</h4>\
                          </div>\
                          <div class=\"panel-body\">\
                              <div class=\"table-responsive\">\
                              <table class=\"table table-striped table-bordered table_rule\" id=\"' + table_id +'\"></table>\
                            </div>\
                          </div>\
                  </div>')
    var table = $("#" + table_id).dataTable({
        "data": data,
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
        // "fnInitComplete": function (oSettings, json) {
        //       $('<button class="btn btn-primary" id="prevent_obj">屏蔽</button> ' + '&nbsp;').appendTo($('.btnBox'));
        // }

    });
    return table;
}

function genTable_by_rule_name(domid, title, table_id, data, columns, solution, rule_name){
    // $("#base").append("<table class=\"table table-striped table-bordered\" id=\"" + table_id + "\"></table>\"")
    $(domid).append('<div class=\"panel panel-inverse\">\
                          <div class=\"panel-heading\">\
                              <h4 class=\"panel-title\">' + title + '</h4>\
                          </div>\
                          <div class=\"panel-body\">\
                          <button class=\"btn btn-primary m-r-5 m-b-5 accordion-toggle accordion-toggle-styled collapsed\" data-toggle=\"collapse\" href=\"#solution_' + rule_name + '\">解决方案</button>\
                            <div id=\"solution_' + rule_name + '\" class=\"panel panel-body panel-collapse collapse\">' + solution + '</div>\
                              <div class=\"table-responsive\">\
                              <table class=\"table table-striped table-bordered table_rule\" id=\"' + table_id +'\"></table>\
                            </div>\
                          </div>\
                  </div>')
    var table = $("#" + table_id).dataTable({
        "data": data,
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
        // "fnInitComplete": function (oSettings, json) {
        //       $('<button class="btn btn-primary" id="prevent_obj">屏蔽</button> ' + '&nbsp;').appendTo($('.btnBox'));
        // }

    });
    return table;
}

function genCharts(title, subtext, legend, rule_mark){
    var myChart;
    // require(['echarts', 'echarts/chart/pie', 'echarts/chart/funnel', 'echarts/chart/line'],
    $("#base").append('<div class=\"panel panel-inverse\">\
                      <div class=\"panel-heading\">\
                          <h4 class=\"panel-title\">' + title + '</h4>\
                      </div>\
                      <div class=\"panel-body\">\
                          <div class=\"table-responsive\">\
                          <div  id=\"rule_mark_pie\" style=\"height:400px\"></div>\
                        </div>\
                      </div>\
              </div>')

    function gen() {
            option = {
                    title : {
                        text: title,
                        subtext: subtext,
                        x: "center"
                    },
                    tooltip : {
                        trigger: 'items',
                        formatter: "{a} <br/>{b} : {c} ({d}分)"
                    },
                    legend: {
                        data: legend,
                        orient : 'vertical',
                        x : 'left',
                    },
                    toolbox: {
                        show : true,
                        feature : {
                            // mark : {show: true},
                            // dataView : {show: true, readOnly: false},
                            restore : {show: true},
                            saveAsImage : {show: true},
                            magicType : {
                            show: true,
                            type: ['pie', 'funnel'],
                            option: {
                                funnel: {
                                    x: '50%',
                                    width: '50%',
                                    funnelAlign: 'left',
                                    max: 1548
                                }
                            }
                        },
                      }
                    },
                    calculable : true,
                    series : [
                        {
                            name: "规则扣分图",
                            type:'pie',
                            radius : '55%',
                            center: ['60%', '60%'],
                            data: rule_mark,
                        }
                    ]
                };
        var myChart = echarts.init(document.getElementById("rule_mark_pie"));
        myChart.setOption(option);
        // return myChart
        // });
        return myChart;
    }
    return gen();
}
function fn_rule_detail(obj){
   var task_uuid = $(obj).attr("task_uuid")
   var rule_name = $(obj).attr("value")
   $.post("/themis/new/version/sql/review/task/rule/detail/info", {"task_uuid": task_uuid, "rule_name": rule_name}, function(result){
      if(result["errcode"] === 80051){
        $("#text_detail").empty();
        $("#plan_detail").empty();
        $("#stat_detail").empty();
        $("#obj_detail").empty();
        if(result["flag"] === "OBJ"){
          var columns = []
          var table_title_length = result["table_title"].length
          for(var i = 0; i < table_title_length; i++){
            columns.push({"title": result["table_title"][i]})
          }
          // columns.push({
          //       "title": "屏蔽处理",
          //       "fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
          //         $(nTd).html("<input type='checkbox' name='rule_detail_list' value='" + sData + "'>");
          //       }
          //     })
          var title_length = result["title"].length
          var title = ""
          for(var i = 0; i < title_length; i++){
            if (!result["title"][i]["parm_desc"]){
              parm_name = "无"
            }else{
              parm_name = result["title"][i]["parm_desc"]
            }
            if (!result["title"][i]["parm_value"]){
              parm_value = "无"
            }else{
              parm_value = result["title"][i]["parm_desc"]
            }
            title +=  "参数：" + parm_name + "  值:" + parm_value
          }
          if (title){
            title = "规则名称: " + result["rule_name"] + " " + title
          }
          else{
            title =  "规则名称: " + result["rule_name"]
          }
          $("#rule_detail").empty()
          genTable_v2("#rule_detail", title, "table_rule_info", result["records"], columns, result["solution"], result["rule_name"])
        }
        else if(result["flag"] === "SQLPLAN" || result["flag"] === "SQLSTAT"){
             var columns = [
                    {
                      "title": "sqlid",
                      "fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
                          $(nTd).html("<a href='#plan_rule_detail' class='plan_rule_detail' task_uuid='" + result["task_uuid"] +"' value='" + sData + "#" + oData[2] + "' onclick='fn_plan_rule_detail(this)'>" + sData + "</a>");
                          }
                    },
                    { "title": "sqltext"},
                    { "title": "plan_hashvalue"},
                    { "title": "pos"},
                    { "title": "object_name"},
                    { "title": "COST"},
                    { "title": "COUNT"}
                  ]
              $("#rule_detail").empty()
              rule_detail_table = genTable_by_rule_name("#rule_detail", result["title"], "plan_table_rule_info", result["records"], columns, result["solution"], result["rule_name"])
        }
        else if(result["flag"] === "TEXT"){
          var columns = [
                    {
                      "title": "sqlid",
                      "fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
                          $(nTd).html("<a href='#plan_rule_detail' class='plan_rule_detail' task_uuid='" + result["task_uuid"] +"' value='" + sData + "#1" + "' onclick='fn_text_rule_detail(this)'>" + sData + "</a>");
                          }
                    },
                    { "title": "sqltext"}
                  ]
            $("#rule_detail").empty()
            rule_detail_table = genTable_by_rule_name("#rule_detail", result["title"], "text_rule_detail", result["records"], columns, result["solution"], result["rule_name"])
        }
      }
   })
}
function fn_plan_rule_detail(obj){
  var task_uuid = $(obj).attr("task_uuid");
  var sql_id_hash = $(obj).attr("value");
  // var html = rule_detail_table.fnGetNodes();
  // var search_str = "a[value='" + sql_id_hash + "']";
  var rule_name = $("#rule_detail").find("h4").text()
  // var node = $(html).find(search_str);
  // var node_list = []
  var id = $($(obj).parent().parent().find("td")[3]).text();
  // for (var i = 0; i < node.length; i++){
  //   var temp = $($(node[i]).parent().parent().find("td")[3]).text();
  //   node_list.push(temp)
  // }
  var json_data = {
      "task_uuid": task_uuid,
      "sql_id_hash": sql_id_hash,
      "id": id,
      "rule_name": rule_name
  }
  $.post("/themis/new/version/sql/review/task/rule/plan/info", JSON.stringify(json_data), function(result){
    if(result["errcode"] === 80054){
      $("#text_detail").empty();
      $("#text_detail").append('<div class=\"panel panel-inverse\">\
                          <div class=\"panel-heading\">\
                              <h4 class=\"panel-title\">SQL文本[sql_id:' + sql_id_hash.split("#")[0] + ']</h4>\
                          </div>\
                          <div class=\"panel-body\">\
                          <textarea id=\"console\" rows=\"8\" class=\"form-control\"></textarea>\
                          </div>\
                  </div>');
      $("#console").val(result["sql_fulltext"]);
      $("#plan_detail").empty();
      // $("#plan_detail").append("<table class=\"table table-hover table-striped table-bordered  dataTable no-footer tree\"><thead><tr>sqlplan</tr><tr>花费</tr></thead></table>")

      if (result["flag"] === "O"){
        $("#plan_detail").append('<div class=\"panel panel-inverse\">\
                    <div class=\"panel-heading\">\
                        <h4 class=\"panel-title\">执行计划</h4>\
                    </div>\
                    <div class=\"panel-body\">\
                        <div class=\"table-responsive\">\
                        <table class=\"table table-striped table-bordered table_rule\" id=\"plan_tree\"><thead><tr><th>sql</th><th>OPTIONS</th><th>OBJECT_OWNER</th><th>OBJECT_NAME</th><th>COST</th><th>ROWS</th></tr></thread></table>\
                      </div>\
                    </div>\
            </div>')
        $.each(result["plan"], function(key, val){
          var td = "<td>" + val["OPERATION_DISPLAY"] + "</td><td>" + val["OPTIONS"] + "</td><td>" + val["OBJECT_OWNER"] + "</td><td>" + val["OBJECT_NAME"] + "</td><td>" + val["COST"] + "</td><td>"+ val["CARDINALITY"] + "</td>";
          if (val["PARENT_ID"] === null){
            var tr=$("<tr></tr>").addClass("treegrid-" + (parseInt(val["ID"]) + 1)).appendTo($('#plan_tree')).html(td);
          }
          else{
            var tr=$("<tr></tr>").addClass("treegrid-" + (parseInt(val["ID"]) + 1)).addClass("treegrid-parent-" + (parseInt(val["PARENT_ID"]) + 1)).appendTo($('#plan_tree')).html(td);
          }
        });
        $("#plan_tree").treegrid({
            expanderExpandedClass: 'glyphicon glyphicon-minus',
            expanderCollapsedClass: 'glyphicon glyphicon-plus'
      });
      }else if(result["flag"] === "mysql"){
        var columns = [
          {"title": "id"},
          {"title": "select_type"},
          {"title": "table"},
          {"title": "type"},
          {"title": "possible_keys"},
          {"title": "key"},
          {"title": "key_len"},
          {"title": "ref"},
          {"title": "rows"},
          {"title": "Extra"}
        ]
        genTable_v3("#plan_detail", "mysql执行计划", "plan_tree", result["plan"], columns);
      }
      if(result["stat_title"].length > 0 && result["stat_data"].length > 0){
        var columns = []
        for (var i = 0; i < result["stat_title"].length; i++){
            columns.push({"title": result["stat_title"][i]})
          }
        $("#stat_detail").empty();
        genTable_v3("#stat_detail", "执行特征", "stat_table_detail", result["stat_data"], columns);
      }
      if(result["obj_title"].length > 0 && result["obj_data"].length > 0){
        var columns = []
        for (var i = 0; i < result["obj_title"].length; i++){
          columns.push({"title": result["obj_title"][i]})
        }
        $("#obj_detail").empty();
        genTable_v3("#obj_detail", "对象信息", "obj_table_detail", result["obj_data"], columns);
      }
    }
  });
}

function fn_text_rule_detail(obj){
  var task_uuid = $(obj).attr("task_uuid");
  var sql_id_hash = $(obj).attr("value");
  var rule_name = $("#rule_detail").find("h4").text();
  var json_data = {
      "task_uuid": task_uuid,
      "sql_id_hash": sql_id_hash,
      "rule_name": rule_name
  }
  $.post("/themis/new/version/sql/review/task/rule/text/info", JSON.stringify(json_data), function(result){
    if(result["errcode"] === 80055){
      $("#text_detail").empty();
      $("#text_detail").append('<div class=\"panel panel-inverse\">\
                          <div class=\"panel-heading\">\
                              <h4 class=\"panel-title\">' + sql_id_hash + '</h4>\
                          </div>\
                          <div class=\"panel-body\">\
                          <textarea id=\"console\" rows=\"8\" class=\"form-control\"></textarea>\
                          </div>\
                  </div>');
      $("#console").val(result["sqltext"]);
      var columns = []
        for (var i = 0; i < result["stat_title"].length; i++){
          columns.push({"title": result["stat_title"][i]})
        }
      $("#stat_detail").empty();
      if(result["stat_list"].length > 0){
        genTable_v3("#stat_detail", "执行特征", "stat_table_detail", result["stat_list"], columns);
      }
    }
  })
}
