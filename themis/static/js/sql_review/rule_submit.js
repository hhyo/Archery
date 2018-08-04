$(document).ready(function() {
    $("#submit").click(function(e){
        e.preventDefault();
        var pathname = window.location.pathname
        var complexity = "simple"
        var rule_cmd
        if (pathname.indexOf("simple") > 0){
            complexity = "simple"
            rule_cmd = $("#rule_sql").val()
        }
        else if(pathname.indexOf("complex") > 0){
            complexity = "complex"
            rule_cmd = "default"
        }
        var in_parms_length = $(".input-fields-wrap .input-parms-desc").length
        var input_parms = []
        if (in_parms_length > 0){
            for (var i = 0; i < in_parms_length; i++){
                input_parms.push({
                    "parm_desc": $($(".input-fields-wrap .input-parms-desc")[i]).val(),
                    "parm_name": $($(".input-fields-wrap .input-parms-name")[i]).val(),
                    "parm_unit": $($(".input-fields-wrap .input-parms-unit")[i]).val(),
                    "parm_value": $($(".input-fields-wrap .input-parms-value")[i]).val()
                })
            }
        }
        var out_parms_length = $(".output-fields-wrap .output-parms-desc").length
        var output_parms = []
        if (out_parms_length > 0){
            for (var i = 0; i < out_parms_length; i++){
                output_parms.push({
                    "parm_desc": $($(".output-fields-wrap .output-parms-desc")[i]).val(),
                    "parm_name": $($(".output-fields-wrap .output-parms-name")[i]).val(),
                })
            }
        }
        var db_type = "mysql"
        if ($("#db_type").val() === "oracle") {
            db_type = "O"
        }
        var data = {
            "rule_cmd": rule_cmd,
            "db_type": db_type,
            "rule_name": $("#rule_name").val(),
            "max_score": $("#max_score").val(),
            "rule_type": $("#rule_type").val(),
            "rule_desc": $("#rule_desc").val(),
            "weight": $("#rule_weight").val(),
            "rule_summary": $("#rule_summary").val(),
            "rule_solution": $("#rule_solution").val(),
            "rule_status": "ON",
            "rule_complexity": complexity,
            "input_parms": input_parms,
            "output_parms": output_parms,
            "exclude_obj_type": $("#exclude_obj_type").val()
        }
        $.post("/themis/sqlreview/rule/addition", JSON.stringify(data), function(result){
            if(result["errcode"] === 80060){
                alert("提交成功")
            }
            else{
                alert(result["message"])
            }
        })
    })
})
