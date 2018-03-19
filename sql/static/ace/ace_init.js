//初始化ace编辑器对象
editor = ace.edit("sql_content_editor");

//设置风格和语言（更多风格和语言，请到github上相应目录查看）
theme = "textmate";
language = "sql";
editor.setTheme("ace/theme/" + theme);
editor.session.setMode("ace/mode/" + language);
editor.$blockScrolling = Infinity;
editor.setValue("");

//字体大小
editor.setFontSize(12);

//设置只读（true时只读，用于展示代码）
editor.setReadOnly(false);

//自动换行,设置为off关闭
editor.setOption("wrap", "free");
editor.getSession().setUseWrapMode(true);

//启用提示菜单
ace.require("ace/ext/language_tools");
editor.setOptions({
    enableBasicAutocompletion: true,
    enableSnippets: true,
    enableLiveAutocompletion: true
});

//绑定快捷键
editor.commands.addCommand({
    name: "alter",
    bindKey: {win: "Ctrl-Enter", mac: "Command-Enter"},
    exec: function (editor) {
        alert(editor.getValue())
    }
});

//设置自动提示代码
var setCompleteData = function (data) {
    var langTools = ace.require("ace/ext/language_tools");
    langTools.addCompleter({
        getCompletions: function (editor, session, pos, prefix, callback) {
            if (prefix.length === 0) {
                return callback(null, []);
            } else {
                return callback(null, data);
            }
        }
    });
};

//增加数据库提示
function setDbsCompleteData(result) {
    if (result) {
        var tables = [];
        for (var i = 0; i < result.length; i++) {
            tables.push({
                name: result[i],
                value: result[i],
                caption: result[i],
                meta: 'databases',
                score: '100'
            });

        }
        setCompleteData(tables);
    }
    else {
        $.ajax({
            type: "post",
            url: "/getdbNameList/",
            dataType: "json",
            data: {
                cluster_name: $("#cluster_name").val()
            },
            complete: function () {
            },
            success: function (data) {
                if (data.status === 0) {
                    var result = data.data;
                    var dbs = [];
                    if (result.length > 0) {
                        for (var i = 0; i < result.length; i++) {
                            dbs.push({
                                name: result[i],
                                value: result[i],
                                caption: result[i],
                                meta: 'databases',
                                score: '100'
                            })
                        }
                        setCompleteData(dbs)
                    }
                } else {
                    alert("status: " + data.status + "\nmsg: " + data.msg + data.data);
                }
            },
            error: function (XMLHttpRequest, textStatus, errorThrown) {
                alert(errorThrown);
            }
        })
    }
}

//增加表提示
function setTablesCompleteData(result) {
    if (result) {
        var tables = [];
        for (var i = 0; i < result.length; i++) {
            tables.push({
                name: result[i],
                value: result[i],
                caption: result[i],
                meta: $("#db_name").val(),
                score: '100'
            });

        }
        setCompleteData(tables);
    }
    else {
        $.ajax({
            type: "post",
            url: "/getTableNameList/",
            dataType: "json",
            data: {
                cluster_name: $("#cluster_name").val(),
                db_name: $("#db_name").val()
            },
            complete: function () {
            },
            success: function (data) {
                if (data.status === 0) {
                    var result = data.data;
                    var tables = [];
                    for (var i = 0; i < result.length; i++) {
                        tables.push({
                            name: result[i],
                            value: result[i],
                            caption: result[i],
                            meta: $("#db_name").val(),
                            score: '100'
                        })
                    }
                    setCompleteData(tables);
                } else {
                    alert("status: " + data.status + "\nmsg: " + data.msg + data.data);
                }
            }
            ,
            error: function (XMLHttpRequest, textStatus, errorThrown) {
                alert(errorThrown);
            }
        });
    }
}

//增加字段提示
function setColumnsCompleteData(result) {
    if (result) {
        var tables = [];
        for (var i = 0; i < result.length; i++) {
            tables.push({
                name: result[i],
                value: result[i],
                caption: result[i],
                meta: $("#table_name").val(),
                score: '100'
            });

        }
        setCompleteData(columns);
    }
    else {
        $.ajax({
            type: "post",
            url: "/getColumnNameList/",
            dataType: "json",
            data: {
                cluster_name: $("#cluster_name").val(),
                db_name: $("#db_name").val(),
                tb_name: $("#table_name").val()
            },
            complete: function () {
            },
            success: function (data) {
                if (data.status === 0) {
                    var result = data.data;
                    var columns = [];
                    for (var i = 0; i < result.length; i++) {
                        columns.push({
                            name: result[i],
                            value: result[i],
                            caption: result[i],
                            meta: $("#table_name").val(),
                            score: '100'
                        })
                    }
                    setCompleteData(columns);
                } else {
                    alert("status: " + data.status + "\nmsg: " + data.msg + data.data);
                }
            }
            ,
            error: function (XMLHttpRequest, textStatus, errorThrown) {
                alert(errorThrown);
            }
        });
    }
}
