var workflowid = $("#workflowDetail_id").val();
var sqlMaxRowNumber = parseInt($("#sqlMaxRowNumber").val());
var wfStatus = -1;
var itemIndex = 1;
var key;
var isStoped = 0;
var retryCnt = 1;

$(document).ready(function (){
  var status = $("#workflowDetail_status").text();
  var isDetail = window.location.pathname.indexOf("detail");
  if (isDetail != -1 && status == "执行中"){
      get_pct(workflowid,itemIndex);

      $("button").click(function (){
        var isContinue = confirm("请确认是否中止pt-OSC进程？");
        if (isContinue) {
            var element = $(this);
            var sqlNum = element.val();
            stopOsc(workflowid, sqlNum);
        }
        });
  };
});

function get_pct(wid, sqlNum){
    if(sqlNum > sqlMaxRowNumber){
         getWorkflowStatus(wid);  //最后一条SQL的进度刷新完后，请求后端接口获取整个工单的状态，如果不为“执行中”状态，则提示刷新当前页面；如果是“执行中”，则每隔1秒查询工单的状态，共重试120次
        // console.log('finish1');
         if (wfStatus != -1 && wfStatus != "执行中") {
             var returned = confirm("执行完毕，请确认是否刷新当前页面？");
                if (returned) {
                    window.location.reload(true);
                }
            }
         else {
                document.getElementById("workflowDetail_status").innerHTML = "确认中...";
                if (retryCnt <= 120){
                     clearTimeout(key);
                     key = setTimeout(function () {
                         get_pct(wid,itemIndex);
                     }, 1000);
                     retryCnt++;
                     }
                else {
                     retryCnt = 1;
                     alert("该工单2分钟仍然未执行完毕，请稍后尝试手动刷新本页面");
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
                //console.log("sqlNum: " + sqlNum);
                //console.log(data);
                if (sqlNum <= sqlMaxRowNumber) {
                    if (data.status == -2) {
                        // 整个工单不由pt-OSC执行
                        return
                    }
                    else if (data.status == 4) {
                        // 不是由pt-OSC执行的，比如DML语句。
                        document.getElementById("td_" + sqlNum).innerHTML = "不由pt-OSC执行";
                        itemIndex++;
                        clearTimeout(key); //1秒后查询下一行的进度值
                        key = setTimeout(function () {
                            get_pct(wid, itemIndex);
                        }, 1000)
                    }
                    else if (data.status == -3) {
                        // 进度未知，2秒重试一次，直到工单状态改变
                        getWorkflowStatus(wid);
                        if (wfStatus != -1 && wfStatus == "执行中") {
                            document.getElementById("div_" + sqlNum).className = "progress";
                            document.getElementById("div_" + sqlNum).style.width = "100%";
                            document.getElementById("span_" + sqlNum).innerHTML = "查询中...";
                            clearTimeout(key);
                            key = setTimeout(function () {
                                get_pct(wid, itemIndex);
                            }, 2000);
                        } else {
                            // 如果工单状态改变，不是“执行中”，则退出重试
                            document.getElementById("div_" + sqlNum).style.width = "100%";
                            document.getElementById("span_" + sqlNum).innerHTML = "未查询到进度";
                            document.getElementById("div_" + sqlNum).className = "progress";
                            return false;
                        }
                    }
                    else if (data.status == 0) {
                        // 在inception能查询到它的进度信息，说明正在执行
                        pct = data.data.percent;
                        // console.log('per:' + pct);
                        document.getElementById("div_" + sqlNum).style.width = pct + "%";
                        document.getElementById("div_" + sqlNum).className = "progress-bar";
                        document.getElementById("span_" + sqlNum).innerHTML = pct + "%";
                        if (pct == 100) {
                            document.getElementById("btnstop_" + sqlNum).style.display = "none";
                            itemIndex++;
                            get_pct(wid, itemIndex);
                        } else {
                            document.getElementById("btnstop_" + sqlNum).style.display = "";
                            clearTimeout(key);
                            key = setTimeout(function () {
                                get_pct(wid, itemIndex);
                            }, 800)
                        }
                    }
                    else {
                        alert(data.msg);
                        return;
                    }
                }
            },
            error: function (XMLHttpRequest, textStatus, errorThrown) {
                alert(errorThrown);
            }
        });
    }
}

function stopOsc(wid, sqlNum){
    if (wid > 0 && sqlNum > 1 && sqlNum <= sqlMaxRowNumber) {
         //console.log('stoping osc...'+ sqlNum);
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
                 //console.log(data);
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
    else{
        alter("参数不正确")
    }
}

function execute(){
    //点击执行之后，刷新当前页面，以显示执行进度
    setTimeout(function(){
        window.location.reload(true);
    },2500)
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

    $("#btnExecute").click(function(){
	$(this).button('loading').delay(2500).queue(function() {
		$(this).button('reset');
		$(this).dequeue();
	});
});
});