$(document).ready(function (){
  var status = $("#workflowDetail_status").text();
  var isDetail = window.location.pathname.indexOf("detail");
  if (isDetail != -1 && status=="执行中"){
      get_pct(workflowid,itemIndex);

      $("button").click(function (){
        var isContinue = confirm("请确认是否中止pt-OSC进程？");
        if (isContinue) {
            var element = $(this);
            var sqlNum = element.val();
            var data = stopOsc(workflowid, sqlNum);
        }
        });

        }
});


var itemIndex = 1;
var workflowid = $("#workflowDetail_id").val();
var sqlMaxRowNumber = parseInt($("#sqlMaxRowNumber").val());
var key;
var isStoped = 0;

function get_pct(wid, sqlNum){
     if(sqlNum > sqlMaxRowNumber){
        // console.log('finish1');
        var returned = confirm("执行完毕，请确认是否刷新当前页面？");
        if (returned){
            window.location.reload(true);
        }
        return;
    }
    if (isStoped == 1){
        document.getElementById("btnstop_" + sqlNum).style.display="none";
        return false;
    }
    var pct;
    $.ajax({
                type: "post",
                async:false,
                url: "/getOscPercent/",
                dataType: "json",
                data: {
                    workflowid: wid,
                    sqlID: sqlNum
                },
                complete: function () {
                },
                success: function (data) {
                    // console.log(data);
                    if (data.status == 4){
                        // 不是由pt-OSC执行的
                        pct = "N/A";
                        document.getElementById("td_" + sqlNum).innerHTML = "不由pt-OSC执行";
                        itemIndex++;
                        clearTimeout(key);
                        key = setTimeout(function(){
                             get_pct(wid,itemIndex);
                        },500)
                    }
                    else if (data.status == 1){
                        // 该行SQL有应对的SHA1值，说明是pt-OSC执行的，但是到inception查询不到它的进度信息，可以判定为执行完毕
                        document.getElementById("btnstop_" + sqlNum).style.display="none";
                        itemIndex++;
                        // console.log('===>' + itemIndex);
                        pct = 100;
                        document.getElementById("div_" + sqlNum).style.width = pct + "%";
                        document.getElementById("span_" + sqlNum).innerHTML = pct + "%";
                        // console.log('per:' + pct);
                        clearTimeout(key);
                        key = setTimeout(function(){
                             get_pct(wid,itemIndex);
                        },500)
                    }
                    else if(data.status == 0){
                        // 在inception能查询到它的进度信息，说明正在执行
                        pct = data.data.percent;
                        // console.log('per:' + pct);
                        document.getElementById("div_" + sqlNum).style.width = pct + "%";
                        document.getElementById("span_" + sqlNum).innerHTML = pct + "%";
                        if(pct == 100){
                           document.getElementById("btnstop_" + sqlNum).style.display="none";
                           itemIndex++;
                           clearTimeout(key);
                           key = setTimeout(function(){
                                 get_pct(wid,itemIndex);
                            },500)
                        }else{
                            document.getElementById("btnstop_" + sqlNum).style.display="";
                            clearTimeout(key);
                            key = setTimeout(function(){
                                 get_pct(wid,sqlNum);
                            },500)
                        }

                    }
                    else{
                        alert(data.msg);
                        return;
                    }
                },
                error: function(XMLHttpRequest, textStatus, errorThrown) {
                    alert(errorThrown);
                }
            });
    return pct;
}

function stopOsc(wid, sqlNum){
    if (wid > 0 && sqlNum > 1 && sqlNum <= sqlMaxRowNumber) {
        // console.log('stoping osc...');
        $.ajax({
            type: "post",
            async: false,
            url: "/stopOscProgress/",
            dataType: "json",
            data: {
                workflowid: wid,
                sqlID: sqlNum
            },
            complete: function () {
            },
            success: function (data) {
                // console.log(data);
                if (data.status == 0) {
                    //改变全局变量isStoped的值，以便停止进度条更新
                    isStoped = 1;
                }
                alert(data.msg);
            },
            error: function (XMLHttpRequest, textStatus, errorThrown) {
                alert(errorThrown);
            }
        });
    }
}

function execute(){
    //点击执行之后，刷新当前页面，以显示执行进度
    clearTimeout(key);
        key = setTimeout(function(){
            window.location.reload(true);
        },1000)
    }

$(document).ready(function () {
    $("#btnEditSql").click(function () {
       var editWorkflowDetailId = $("#workflowDetail_id").val();
       var editWorkflowNname = $("#editWorkflowNname").text();
       var editSqlContent = $("#editSqlContent").val();
       sessionStorage.setItem('editWorkflowDetailId', editWorkflowDetailId);
       sessionStorage.setItem('editWorkflowNname', editWorkflowNname);
       sessionStorage.setItem('editSqlContent', editSqlContent);
    });

});