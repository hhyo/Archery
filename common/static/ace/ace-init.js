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
    bindKey: { win: "Ctrl-Enter", mac: "Command-Enter" },
    exec: function (editor) {
        let pathname = window.location.pathname;
        if (pathname === "/sqlquery/") {
            dosqlquery()
        }
    }
});

// 监听输入，强制在输入点号时触发自动补全
editor.commands.on("afterExec", function (e) {
    if (e.command.name === "insertstring" && e.args === ".") {
        editor.execCommand("startAutocomplete");
    }
});

//设置自动提示代码
var archeryAutoCompleteData = {
    database: [],
    schema: [],
    table: [],
    column: []
};
var isCompleterAdded = false;

var setCompleteData = function (data, type) {
    var langTools = ace.require("ace/ext/language_tools");

    if (type) {
        archeryAutoCompleteData[type] = data;
    }

    if (!isCompleterAdded) {
        langTools.addCompleter({
            // 增加点号作为触发字符
            triggerCharacters: ['.'],
            getCompletions: function (editor, session, pos, prefix, callback) {
                // 1. 获取光标之前的文本，判断是否是点号触发或点号后继续输入
                var line = session.getLine(pos.row);
                var textBeforeCursor = line.slice(0, pos.column);
                var match = textBeforeCursor.match(/([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]*)$/);

                if (match) {
                    var alias = match[1]; // 可能是别名，也可能是表名
                    var fullSql = session.getValue();
                    var tableName = null;

                    // 2. 正则解析 SQL 获取表名与别名的映射 (from/join/逗号 表名 [as] 别名)
                    var tableMatchRegex = /(?:from|join|,)\s+([a-zA-Z0-9_.\`]+)\s+(?:as\s+)?([a-zA-Z0-9_`]+)/gi;
                    var m;
                    while ((m = tableMatchRegex.exec(fullSql)) !== null) {
                        var matchedAlias = m[2].replace(/`/g, '');
                        if (matchedAlias === alias) {
                            tableName = m[1].replace(/`/g, '');
                            break;
                        }
                    }

                    // 如果没找到对应的别名，可能用户直接使用了 "表名." 
                    if (!tableName) {
                        var tableDirectRegex = /(?:from|join|,)\s+([a-zA-Z0-9_.\`]+)/gi;
                        while ((m = tableDirectRegex.exec(fullSql)) !== null) {
                            var matchedTable = m[1].replace(/`/g, '');
                            if (matchedTable === alias) {
                                tableName = matchedTable;
                                break;
                            }
                        }
                    }

                    if (tableName) {
                        // 处理可能带库名/模式名的情况 (如 db.table 取 table)
                        if (tableName.indexOf('.') !== -1) {
                            var parts = tableName.split('.');
                            tableName = parts[parts.length - 1];
                        }

                        // 3. 尝试从已缓存的 column 数据中查找
                        var cachedColumns = archeryAutoCompleteData.column.filter(function (c) {
                            return c.meta === tableName;
                        });

                        if (cachedColumns.length > 0) {
                            return callback(null, cachedColumns);
                        } else {
                            // 4. 缓存中没有，发起 Ajax 请求实时获取该表的字段
                            var instance_name = $("#instance_name").val();
                            var db_name = $("#db_name").val();
                            if (!instance_name) return callback(null, []);

                            $.ajax({
                                type: "get",
                                url: "/api/v1/sqlquery/resources/",
                                dataType: "json",
                                data: {
                                    instance_name: instance_name,
                                    db_name: db_name,
                                    schema_name: $("#schema_name").val(),
                                    tb_name: tableName,
                                    resource_type: "column"
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
                                                meta: tableName,
                                                score: 100
                                            });
                                        }
                                        // 合并到缓存中，下次直接使用
                                        archeryAutoCompleteData.column = archeryAutoCompleteData.column.concat(columns);
                                        callback(null, columns);
                                    } else {
                                        callback(null, []);
                                    }
                                },
                                error: function () {
                                    callback(null, []);
                                }
                            });
                            return; // 异步请求，直接返回等待 callback
                        }
                    }
                }

                // 默认的补全逻辑
                if (prefix.length === 0) {
                    return callback(null, []);
                } else {
                    var allData = archeryAutoCompleteData.database.concat(
                        archeryAutoCompleteData.schema,
                        archeryAutoCompleteData.table,
                        archeryAutoCompleteData.column
                    );
                    return callback(null, allData);
                }
            }
        });
        isCompleterAdded = true;
    }
};

//增加数据库提示
function setDbsCompleteData(result) {
    var dbs = [];
    for (var i = 0; i < result.length; i++) {
        dbs.push({
            name: result[i],
            value: result[i],
            caption: result[i],
            meta: "database",
            score: 100
        });

    }
    setCompleteData(dbs, "database");
}

//增加模式提示
function setSchemasCompleteData(result) {
    var schemas = [];
    for (var i = 0; i < result.length; i++) {
        schemas.push({
            name: result[i],
            value: result[i],
            caption: result[i],
            meta: "schema",
            score: 100
        });

    }
    setCompleteData(schemas, "schema");
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
    setCompleteData(tables, "table");
}

//增加字段提示
function setColumnsCompleteData(result) {
    if (result) {
        var columns = [];
        for (var i = 0; i < result.length; i++) {
            columns.push({
                name: result[i],
                value: result[i],
                caption: result[i],
                meta: $("#table_name").val(),
                score: 100
            });

        }
        setCompleteData(columns, "column");
    } else {
        $.ajax({
            type: "get",
            url: "/api/v1/sqlquery/resources/",
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
                    setCompleteData(columns, "column");
                } else {
                    alert(data.msg);
                }
            }
        });
    }
}

// 实例变更时修改language
$("#instance_name").change(function () {
    // 清空所有的自动补全数据
    archeryAutoCompleteData.database = [];
    archeryAutoCompleteData.schema = [];
    archeryAutoCompleteData.table = [];
    archeryAutoCompleteData.column = [];

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

// 数据库变更时，清空表和字段的自动补全数据
$("#db_name").change(function () {
    archeryAutoCompleteData.table = [];
    archeryAutoCompleteData.column = [];
});

// 模式(Schema)变更时，清空表和字段的自动补全数据
$("#schema_name").change(function () {
    archeryAutoCompleteData.table = [];
    archeryAutoCompleteData.column = [];
});

