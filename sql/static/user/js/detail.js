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
var wfStatus = -1;
var retryCnt = 1;
var executing = 0;

function get_pct(wid, sqlNum){
     if(sqlNum > sqlMaxRowNumber){
         getWorkflowStatus(wid);  //最后一条SQL的进度刷新完后，请求后端接口获取整个工单的状态，如果不为“执行中”状态，则提示刷新当前页面；如果是“执行中”，则每隔1秒查询工单的状态，共重试60次
        // console.log('finish1');
         if (wfStatus != -1 && wfStatus != "执行中") {
             var returned = confirm("执行完毕，请确认是否刷新当前页面？");
                if (returned) {
                    window.location.reload(true);
                }
            }else {
                document.getElementById("workflowDetail_status").innerHTML = "确认中...";
                if (retryCnt <= 60){
                     clearTimeout(key);
                     key = setTimeout(function () {
                         get_pct(wid, sqlNum);
                     }, 1000);
                     retryCnt++;
                     }
                else {
                     retryCnt = 1;
                     alert("该工单一分钟仍然未执行完毕，请稍后尝试手动刷新本页面");
                     }

            }
     }

    else {

         if (isStoped == 1) {
             document.getElementById("btnstop_" + sqlNum).style.display = "none";
             return false;
         }
         var pct;
         $.ajax({
             type: "post",
             async: false,
             url: "/getOscPercent/",
             dataType: "json",
             data: {
                 workflowid: wid,
                 sqlID: sqlNum
             },
             complete: function () {
             },
             success: function (data) {
                  //console.log(data);
                 if (data.status == 4) {
                     // 不是由pt-OSC执行的，比如DML语句
                     pct = "N/A";
                     document.getElementById("td_" + sqlNum).innerHTML = "不由pt-OSC执行";
                     itemIndex++;
                     executing = 0;
                     clearTimeout(key);
                     key = setTimeout(function () {
                         get_pct(wid, itemIndex);
                     }, 1000)
                 }
                 else if (data.status == 1) {
                     // 该行SQL有应对的SHA1值，说明该SQL会由pt-OSC执行，但是到inception查询不到它的进度信息；有2种情况：
                     // 1.正在执行DML语句，inception实际还未执行到这一行，只是本js轮循到这一行了而已
                     // 2.已执行完毕
                     if (executing == 0) {
                         //第1种情况,这里进行5次重试，每次间隔1秒
                         if (retryCnt <= 5) {
                             clearTimeout(key);
                             //document.getElementById("span_" + sqlNum).style.color = "#F00";
                             document.getElementById("div_" + sqlNum).className = "progress";
                             document.getElementById("div_" + sqlNum).style.width = "100%";
                             document.getElementById("span_" + sqlNum).innerHTML = "查询中...";
                             key = setTimeout(function () {
                                 get_pct(wid, itemIndex);
                             }, 1000);
                             //console.log("retryCnt: " + retryCnt + ",itemIndex: " + itemIndex);
                             retryCnt++;
                         } else {
                             retryCnt = 1;
                             document.getElementById("div_" + sqlNum).className = "progress-bar";
                             itemIndex++;
                             executing = 0;
                             // console.log('===>' + itemIndex);
                             pct = 100;
                             document.getElementById("div_" + sqlNum).style.width = pct + "%";
                             document.getElementById("span_" + sqlNum).innerHTML = pct + "%";
                             get_pct(wid, itemIndex);
                             // console.log('per:' + pct);
                         }
                     }else{
                         //第2种情况
                         document.getElementById("btnstop_" + sqlNum).style.display = "none";
                         itemIndex++;
                         executing = 0;
                         pct = 100;
                         document.getElementById("div_" + sqlNum).style.width = pct + "%";
                         document.getElementById("span_" + sqlNum).innerHTML = pct + "%";
                         get_pct(wid, itemIndex);
                     }
                 }
                 else if (data.status == 0) {
                     // 在inception能查询到它的进度信息，说明正在执行
                     pct = data.data.percent;
                     // console.log('per:' + pct);
                     document.getElementById("div_" + sqlNum).className = "progress-bar";
                     document.getElementById("div_" + sqlNum).style.width = pct + "%";
                     document.getElementById("span_" + sqlNum).innerHTML = pct + "%";
                     executing = 1;
                     if (pct == 100) {
                         document.getElementById("btnstop_" + sqlNum).style.display = "none";
                         itemIndex++;
                         executing = 0;
                         clearTimeout(key);
                         key = setTimeout(function () {
                             get_pct(wid, itemIndex);
                         }, 800)
                     } else {
                         document.getElementById("btnstop_" + sqlNum).style.display = "";
                         clearTimeout(key);
                         key = setTimeout(function () {
                             get_pct(wid, sqlNum);
                         }, 800)
                     }

                 }
                 else {
                     alert(data.msg);
                     return;
                 }

             },
             error: function (XMLHttpRequest, textStatus, errorThrown) {
                 alert(errorThrown);
             }
         });
         return pct;
     }
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

function getWorkflowStatus(wid){
    if (wid > 0) {
        // console.log('get workflow status');
        $.ajax({
            type: "post",
            async: false,
            url: "/getWorkflowStatus/",
            dataType: "json",
            data: {
                workflowid: wid
            },
            complete: function () {
            },
            success: function (data) {
                wfStatus = data.status;
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