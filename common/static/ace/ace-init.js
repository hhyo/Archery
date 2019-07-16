//初始化ace编辑器对象
editor = ace.edit("sql_content_editor");

//设置风格和语言（更多风格和语言，请到github上相应目录查看）
theme = "textmate";
language = "mysql"; // TODO 可以按照实例类型自动变更
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
        sqlquery();
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
    var tables = [];
    for (var i = 0; i < result.length; i++) {
        tables.push({
            name: result[i],
            value: result[i],
            caption: result[i],
            meta: "database",
            score: 100
        });

    }
    setCompleteData(tables);
}

//增加模式提示
function setSchemasCompleteData(result) {
    var tables = [];
    for (var i = 0; i < result.length; i++) {
        tables.push({
            name: result[i],
            value: result[i],
            caption: result[i],
            meta: "schema",
            score: 100
        });

    }
    setCompleteData(tables);
}


//增加表提示
function setTablesCompleteData(result) {
    var meta = $("#db_name").val();
    if ($("#schema_name").val()) {
        meta = $("#schema_name").val();
    }
    var tables = [];
    for (var i = 0; i < result.length; i++) {
        tables.push({
            name: result[i],
            value: result[i],
            caption: result[i],
            meta: meta,
            score: 100
        });

    }
    setCompleteData(tables);
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
                score: 100
            });

        }
        setCompleteData(columns);
    } else {
        $.ajax({
            type: "post",
            url: "/instance/instance_resource/",
            dataType: "json",
            data: {
                instance_name: $("#instance_name").val(),
                db_name: $("#db_name").val(),
                schema_name: $("#schema_name").val(),
                tb_name: $("#table_name").val(),
                resource_type: "column"
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
                            score: 100
                        })
                    }
                    setCompleteData(columns);
                } else {
                    alert(data.msg);
                }
            }
        });
    }
}
