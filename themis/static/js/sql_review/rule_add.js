$(document).ready(function() {
    var input_max_fields = 5; //maximum input boxes allowed
    var output_max_fields = 30;
    var input_wrapper = $(".input-fields-wrap"); //Fields wrapper
    var add_input_button = $(".add-input-field-button"); //Add button ID
    var reduce_input_button = $(".reduce-input-field-button"); //reduce button ID
    var output_wrapper = $(".output-fields-wrap");
    var add_output_button = $(".add-output-field-button");
    var reduce_output_button = $(".reduce-output-field-button")
    
    var input_x = 0; //initlal text box count
    $(add_input_button).click(function(e){ //on add input button click
        e.preventDefault();
        if(input_x < input_max_fields){ //max input box allowed
            input_x++; //text box increment
            $(input_wrapper).append('<div class=\"input-parms-padding col-md-12\">\
                                <div class=\"input-parms input-parms-padding col-md-6\">\
                                     <div class=\"col-md-12 form-group\">\
                                        <label for=\"input_parms\">参数描述</label>\
                                        <input type=\"text\" class=\"form-control input-parms-desc\" placeholder=\"参数描述\" />\
                                    </div>\
                                </div>\
                                <div class=\"input-parms input-parms-padding col-md-6\">\
                                    <div class=\"col-md-12 form-group\">\
                                        <label for=\"input_parms\">参数名称</label>\
                                        <input type=\"text\" class=\"form-control input-parms-name\" placeholder=\"参数名称\" />\
                                    </div>\
                                </div>\
                                </div>\
                                <div class=\"input-parms-padding col-md-12\">\
                                <div class=\"input-parms input-parms-padding col-md-6\">\
                                     <div class=\"col-md-12 form-group\">\
                                        <label for=\"input_parms\">参数单位</label>\
                                        <input type=\"text\" class=\"form-control input-parms-unit\" placeholder=\"参数单位\" />\
                                    </div>\
                                </div>\
                                <div class=\"input-parms input-parms-padding col-md-6\">\
                                    <div class=\"col-md-12 form-group\">\
                                        <label for=\"input_parms\">参数值</label>\
                                        <input type=\"text\" class=\"form-control input-parms-value\" placeholder=\"参数值\" />\
                                    </div>\
                                </div>\
                            </div>'); //add input box
        }
    });
    output_x = 0;
    $(add_output_button).click(function(e){
        e.preventDefault();
        if(output_x < output_max_fields){
            output_x++;
            $(output_wrapper).append('<div class=\"output-parms-padding col-md-12\">\
                                    <div class=\"output-parms output-parms-padding col-md-6\">\
                                         <div class=\"col-md-12 form-group\">\
                                            <label for=\"output_parms\">参数描述</label>\
                                            <input type=\"text\" class=\"form-control output-parms-desc\" placeholder=\"参数描述\" />\
                                        </div>\
                                    </div>\
                                    <div class=\"output-parms output-parms-padding col-md-6\">\
                                        <div class=\"col-md-12 form-group\">\
                                            <label for=\"output_parms\">参数名称</label>\
                                            <input type=\"text\" class=\"form-control output-parms-name\" placeholder=\"参数名称\" />\
                                        </div>\
                                    </div>\
                                    </div>')
        }
    })
    $(reduce_input_button).click(function(e){
        e.preventDefault()
        var input_parms_length = $(".input-parms").length;
        if (input_parms_length === 0){
            alert("没有参数可减少")
            return;
        }
        else{
            $($(".input-parms")[input_parms_length - 1]).parent().remove();
            $($(".input-parms")[input_parms_length - 1 - 2]).parent().remove();
            return;
        }
    })
    $(reduce_output_button).click(function(e){
        e.preventDefault()
        var output_parms_length = $(".output-parms").length;
        if (output_parms_length === 0){
            alert("没有参数可减少")
            return;
        }
        else{
            $($(".output-parms")[output_parms_length - 1]).parent().remove();
            return;
        }
    })
});
