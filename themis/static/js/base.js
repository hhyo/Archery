
// level: alert-success alert-waring alert-info alert-danger
function print_message(domid, level, message){
    $("#" + domid).empty();
    $("#" + domid).append('<div class=\"alert ' + level + ' fade in m-b-15\"> ' + message +
                                '<span class=\"close\" data-dismiss=\"alert\">&times;</span>\
                            </div>')
    $("#" +domid).show();
}