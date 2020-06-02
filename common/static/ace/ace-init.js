//初始化ace编辑器对象
var editor = ace.edit("sql_content_editor");
ace.config.set('basePath', '/static/ace');
ace.config.set('modePath', '/static/ace');
ace.config.set('themePath', '/static/ace');

//设置风格和语言（更多风格和语言，请到github上相应目录查看）
var theme = "textmate";
var language = "text";
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

//启用搜索扩展
ace.require("ace/ext/language_tools");

//绑定查询快捷键
editor.commands.addCommand({
    name: "alter",
    bindKey: {win: "Ctrl-Enter", mac: "Command-Enter"},
    exec: function (editor) {
        let pathname = window.location.pathname;
        if (pathname === "/sqlquery/") {
            sqlquery();
        }
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
            type: "get",
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

// 实例变更时修改language
$("#instance_name").change(function () {
    let optgroup = $('#instance_name :selected').parent().attr('label');
    if (optgroup === "MySQL") {
        editor.setTheme("ace/theme/" + "textmate");
        editor.session.setMode("ace/mode/" + "mysql");
        // 提示信息
        let pathname = window.location.pathname;
        if (pathname === "/submitsql/" && !editor.getValue()) {
            editor.setValue("-- 请在此输入SQL，以分号结尾，仅支持DML和DDL语句，查询语句请使用SQL查询功能。\n");
            editor.clearSelection();
            editor.focus();  //获取焦点
        }
    } else if (optgroup === "MsSQL") {
        editor.setTheme("ace/theme/" + "sqlserver");
        editor.session.setMode("ace/mode/" + "sqlserver");
    } else if (optgroup === "Redis") {
        editor.setTheme("ace/theme/" + "textmate");
        editor.session.setMode("ace/mode/" + "text");
        editor.setOptions({
            enableSnippets: false,
        });
        // 提示信息
        let pathname = window.location.pathname;
        if (pathname === "/submitsql/" && !editor.getValue()) {
            editor.setValue("请在此输入命令，多个命令请换行填写，在提交时请删除此行说明");
            editor.focus();  //获取焦点
        }
    } else if (optgroup === "PgSQL") {
        editor.setTheme("ace/theme/" + "textmate");
        editor.session.setMode("ace/mode/" + "pgsql");
    } else if (optgroup === "Oracle") {
        editor.setTheme("ace/theme/" + "textmate");
        editor.session.setMode("ace/mode/" + "sql");
    } else if (optgroup === "Mongo") {
        editor.setTheme("ace/theme/" + "textmate");
        editor.session.setMode("ace/mode/" + "mongodb");
        editor.setOptions({
            enableSnippets: false,
        });
    } else {
        editor.setTheme("ace/theme/" + "textmate");
        editor.session.setMode("ace/mode/" + "mysql");
    }
});
