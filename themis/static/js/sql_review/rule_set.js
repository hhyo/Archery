var test;
$(document).ready(function() {
  //  $('.nav-tabs a').click(function (e) {
  //     e.preventDefault()
  //     var flag = 0;
  //     if($(this).attr("href") === "#nav-tab-1"){
  //       flag = 1
  //     }
  //     else if($(this).attr("href") === "#nav-tab-2"){
  //       flag = 2;
  //     }
  //     else if($(this).attr("href") === "#nav-tab-3"){
  //       flag = 3;
  //     }
  //     else if($(this).attr("href") === "#nav-tab-4"){
  //       flag = 4
  //     }
  //     else{
  //     }
  //     if (flag != 0){

  //     }
  // })
      $.get("/themis/sqlreview/rule/info", {}, function(result){
        if(result["errcode"] === 80013){
           var columns = [
              {"title": "规则名称"},
              {"title": "规则概要"},
              {
                 "title": "规则状态",
                  "fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
                    $(nTd).addClass('inputType').attr('dbtype', oData[6]);
                   $(nTd).addClass('selectTd').attr('id', oData[0] + "$status");
                 }
              },
              {
                "title": "权重",
                "fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
                           $(nTd).addClass('inputWeight').attr('dbtype', oData[6]);
                           $(nTd).addClass('inputWeight').attr('id', oData[0] + "$weight")
                         }
              },
              {
                 "title": "最高分",
                  "fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
                   $(nTd).addClass('inputMax').attr('dbtype', oData[6]);
                   $(nTd).addClass('inputMax').attr('id', oData[0] + "$maxscore");
                 }
              },
              {"title": "规则类型"},
              {"title": "db type"},
              {
                 "title": "参数一",
                  "fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
                   $(nTd).addClass('inputParm1').attr('dbtype', oData[6]);
                   $(nTd).addClass('inputParm1').attr('id', oData[0] + "$parm1");
                 }
              },
              {
                 "title": "参数二",
                  "fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
                   $(nTd).addClass('inputParm2').attr('dbtype', oData[6]);
                   $(nTd).addClass('inputParm2').attr('id', oData[0] + "$parm2");
                 }
              },
               {
                 "title": "参数三",
                  "fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
                   $(nTd).addClass('inputParm3').attr('dbtype', oData[6]);
                   $(nTd).addClass('inputParm3').attr('id', oData[0] + "$parm3");
                 }
              },
               {
                 "title": "RuleCmd",
                  "fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
                   $(nTd).addClass('RuleCmd').attr('dbtype', oData[6]);
                   $(nTd).addClass('RuleCmd').attr('id', oData[0] + "$rule_cmd");
                 }
              }
           ]
           genTable("struct", "struct_table", result["data"], columns)
        }
     })
});

function genTable(domid, table_id, data, columns){
    $("#" + domid).empty();
    $("#" + domid).append('<table class=\"table table-striped table-bordered table_rule\" id=\"' + table_id + '\"></table>')
    var table = $("#" + table_id).dataTable({
        "data": data,
        // "columns": columns    
        "columns" : columns,
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
         "fnDrawCallback": function (data, x) {
            $('#' + table_id + ' tbody td.inputMax').
              editable('/new/version/sql/review/rule/info', {
                        method: "POST",
                        submitdata: function(value, settings) {
                          return {
                                  oldvalue: value,
                                  dbtype: $(this).attr("dbtype"),
                                  flag: "maxscore"
                                };
                        },
                         callback: function(value, settings) {
                            var result = JSON.parse(value)
                            if (result["errcode"] === 80025){
                              $(this).text(function(){ return result["data"]})
                            }
                            else{
                              alert(result["message"])
                              $(this).text(function(){ return 0})
                            }
                        }
                      });
            $('#' + table_id + ' tbody td.selectTd').
            editable('/themis/sqlreview/rule/info', {
                      method: "POST",
                      data:{"ON": "ON", "OFF": "OFF"},
                      submitdata: function(value, settings) {
                        return {
                                oldvalue: value,
                                dbtype: $(this).attr("dbtype"),
                                flag: "status"
                              };
                      },
                      callback: function(value, settings) {
                          var result = JSON.parse(value)
                          if (result["errcode"] === 80025){
                            $(this).text(function(){ return result["data"]})
                          }
                          else{
                            alert(result["message"])
                            $(this).text(function(){ return "error"})
                          }
                      },
                      type: 'select',
                      submit: 'OK'
                    });
            $('#' + table_id + ' tbody td.inputWeight').
            editable('/themis/sqlreview/rule/info', {
              method: "POST",
              submitdata: function(value, settings) {
                return {
                        oldvalue: value,
                        dbtype: $(this).attr("dbtype"),
                        flag: "weight"
                      };
              },
               callback: function(value, settings) {
                  var result = JSON.parse(value)
                  if (result["errcode"] === 80025){
                    $(this).text(function(){ return result["data"]})
                  }
                  else{
                    alert(result["message"])
                    $(this).text(function(){ return 0})
                  }
              }
            });
            $('#' + table_id + ' tbody td.inputParm1').
            editable('/themis/sqlreview/rule/info', {
              method: "POST",
              submitdata: function(value, settings) {
                return {
                        oldvalue: value,
                        dbtype: $(this).attr("dbtype"),
                        flag: "parm1"
                      };
              },
               callback: function(value, settings) {
                  var result = JSON.parse(value)
                  if (result["errcode"] === 80025){
                    $(this).text(function(){ return result["data"]})
                  }
                  else{
                    alert(result["message"])
                    $(this).text(function(){ return 0})
                  }
              }
            });
             $('#' + table_id + ' tbody td.inputParm2').
            editable('/themis/sqlreview/rule/info', {
              method: "POST",
              submitdata: function(value, settings) {
                return {
                        oldvalue: value,
                        dbtype: $(this).attr("dbtype"),
                        flag: "parm2"
                      };
              },
               callback: function(value, settings) {
                  var result = JSON.parse(value)
                  if (result["errcode"] === 80025){
                    $(this).text(function(){ return result["data"]})
                  }
                  else{
                    alert(result["message"])
                    $(this).text(function(){ return 0})
                  }
              }
            });
               $('#' + table_id + ' tbody td.inputParm3').
            editable('/themis/sqlreview/rule/info', {
              method: "POST",
              submitdata: function(value, settings) {
                return {
                        oldvalue: value,
                        dbtype: $(this).attr("dbtype"),
                        flag: "parm3"
                      };
              },
               callback: function(value, settings) {
                  var result = JSON.parse(value)
                  if (result["errcode"] === 80025){
                    $(this).text(function(){ return result["data"]})
                  }
                  else{
                    alert(result["message"])
                    $(this).text(function(){ return 0})
                  }
              }
            });
             $('#' + table_id + ' tbody td.RuleCmd').
            editable('/themis/sqlreview/rule/info', {
              method: "POST",
              submitdata: function(value, settings) {
                return {
                        oldvalue: value,
                        dbtype: $(this).attr("dbtype"),
                        flag: "rule_cmd"
                      };
              },
               callback: function(value, settings) {
                  var result = JSON.parse(value)
                  if (result["errcode"] === 80025){
                    $(this).text(function(){ return result["data"]})
                  }
                  else{
                    alert(result["message"])
                    $(this).text(function(){ return 0})
                  }
              }
            });
        }
    });
    return table;
}
