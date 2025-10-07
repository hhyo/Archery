const pgsqlDiagnosticInfo = {
    fieldsProcesslist: [
        'pgsql',
        ["All", "Not Idle"],
        [
            { title: '', field: 'checkbox', checkbox: true },
            { title: 'PId', field: 'pid', sortable: true },
            { title: '阻塞PID', field: 'block_pids', sortable: false },
            { title: '数据库', field: 'datname', sortable: true },
            { title: '用户', field: 'usename', sortable: true },
            { title: '应用名称', field: 'application_name', sortable: true },
            { title: '状态', field: 'state', sortable: true },
            { title: '客户端地址', field: 'client_addr', sortable: true },
            { title: '耗时(秒)', field: 'elapsed_time_seconds', sortable: true },
            { title: '耗时', field: 'elapsed_time', sortable: true },
            { title: '查询语句', field: 'query', sortable: true },
            { title: '等待事件类型', field: 'wait_event_type', sortable: true },
            { title: '等待事件', field: 'wait_event', sortable: true },
            { title: '查询开始时间', field: 'query_start', sortable: true },
            { title: '后端开始时间', field: 'backend_start', sortable: true },
            { title: '父PID', field: 'leader_pid', sortable: true },
            { title: '客户端主机名', field: 'client_hostname', sortable: true },
            { title: '客户端端口', field: 'client_port', sortable: true },
            { title: '事务开始时间', field: 'transaction_start_time', sortable: true },
            { title: '状态变更时间', field: 'state_change', sortable: true },
            { title: '后端XID', field: 'backend_xid', sortable: true },
            { title: '后端XMIN', field: 'backend_xmin', sortable: true },
            { title: '后端类型', field: 'backend_type', sortable: true },
        ]
    ],

}

const mysqlDiagnosticInfo = {
    fieldsProcesslist: [
        'mysql',
        ["All", "Not Sleep", "Query"],
        [{
            title: '',
            field: 'checkbox',
            checkbox: true
        }, {
            title: 'THEEAD ID',
            field: 'id',
            sortable: true
        }, {
            title: 'USER',
            field: 'user',
            sortable: true
        }, {
            title: 'HOST',
            field: 'host',
            sortable: true
        }, {
            title: 'DATABASE',
            field: 'db',
            sortable: true
        }, {
            title: 'TIME(s)',
            field: 'time',
            sortable: true
        }, {
            title: 'COMMAND',
            field: 'command',
            sortable: true
        }, {
            title: 'STATE',
            field: 'state',
            sortable: true
        }, {
            title: 'INFO',
            field: 'info',
            sortable: true,
            formatter: function (value, row, index) {
                if (value.length > 20) {
                    var sql = value.substr(0, 20) + '...';
                    return sql;
                } else {
                    return value
                }
            }
        }, {
            title: '完整INFO',
            field: 'info',
            sortable: true,
            visible: false // 默认不显示
        }],
        function (index, row) {
            var html = [];
            $.each(row, function (key, value) {
                if (key === 'info') {
                    var sql = window.sqlFormatter.format(value);
                    //替换所有的换行符
                    sql = sql.replace(/\r\n/g, "<br>");
                    sql = sql.replace(/\n/g, "<br>");
                    //替换所有的空格
                    sql = sql.replace(/\s/g, "&nbsp;");
                    html.push('<span>' + sql + '</span>');
                }
            });
            return html.join('');
        }
    ],
}

const mongoDiagnosticInfo = {
    fieldsProcesslist: [
        'mongo',
        ["All", "Active", "Full", "Inner"],
        [{
            title: '',
            field: 'checkbox',
            checkbox: true
        }, {
            title: 'opid',
            field: 'opid',
            sortable: true
        }, {
            title: 'client',
            field: 'client',
            sortable: true
        }, {
            title: 'client_s',
            field: 'client_s',
            sortable: true
        }, {
            title: 'type',
            field: 'type',
            sortable: true
        }, {
            title: 'active',
            field: 'active',
            sortable: true
        }, {
            title: 'desc',
            field: 'desc',
            sortable: true
        }, {
            title: 'ns',
            field: 'ns',
            sortable: true
        }, {
            title: 'effectiveUsers_user',
            field: 'effectiveUsers_user',
            sortable: true
        }
            , {
            title: 'secs_running',
            field: 'secs_running',
            sortable: true
        }
            , {
            title: 'microsecs_running',
            field: 'microsecs_running',
            sortable: true
        }, {
            title: 'waitingForLock',
            field: 'waitingForLock',
            sortable: true

        }, {
            title: 'locks',
            field: 'locks',
            sortable: true,
            formatter: function (value, row, index) {
                return JSON.stringify(value);
            },
            visible: false
        }, {
            title: 'lockStats',
            field: 'lockStats',
            sortable: true,
            formatter: function (value, row, index) {
                return JSON.stringify(value);
            },
            visible: false
        }, {
            title: 'command',
            field: 'command',
            sortable: true,
            formatter: function (value, row, index) {
                if (value) {
                    let c = JSON.stringify(value);
                    if (c.length > 20) {
                        return c.substr(0, 80) + '...}';
                    } else {
                        return c;
                    }
                }
            }
        }, {
            title: '完整command',
            field: 'command',
            sortable: true,
            formatter: function (value, row, index) {
                return JSON.stringify(value);
            },
            visible: false // 默认不显示
        }, {
            title: 'clientMetadata',
            field: 'clientMetadata',
            sortable: true,
            formatter: function (value, row, index) {
                return JSON.stringify(value);
            },
            visible: false // 默认不显示
        }],
        function (index, row) {
            delete row['checkbox'];
            return "<pre>" + jsonHighLight(JSON.stringify(row, null, 2)) + "</pre>";
        }
    ],
}

const redisDiagnosticInfo = {
    fieldsProcesslist: [
        'redis',
        ["All"],
        [{
            title: '',  // 用于多选框
            field: 'checkbox',
            checkbox: true
        }, {
            title: 'Id',
            field: 'id',
            sortable: true
        }, {
            title: '远程地址',
            field: 'addr',
            sortable: true
        }, {
            title: '本地地址',
            field: 'laddr',
            sortable: true
        }, {
            title: '客户端名称',
            field: 'name',
            sortable: true
        }, {
            title: '用户',
            field: 'user',
            sortable: true
        },
        {
            title: '数据库',
            field: 'db',
            sortable: true
        }, {
            title: '连接耗时(秒)',
            field: 'age',
            sortable: true
        }, {
            title: '空闲时间(秒)',
            field: 'idle',
            sortable: true
        }, {
            title: '命令',
            field: 'cmd',
            sortable: true
        }, {
            title: '总内存',
            field: 'tot-mem',
            sortable: true
        }, {
            title: '输出内存',
            field: 'omem',
            sortable: true
        }, {
            title: '标志',
            field: 'flags',
            sortable: true
        }, {
            title: '文件描述符',
            field: 'fd',
            sortable: true
        }, {
            title: '订阅数',
            field: 'sub',
            sortable: true
        }, {
            title: '模式订阅数',
            field: 'psub',
            sortable: true
        }, {
            title: 'MULTI 队列长度',
            field: 'multi',
            sortable: true
        }, {
            title: '查询缓冲区',
            field: 'qbuf',
            sortable: true
        }, {
            title: '查询缓冲区空闲',
            field: 'qbuf-free',
            sortable: true
        }, {
            title: '参数内存',
            field: 'argv-mem',
            sortable: true
        }, {
            title: '输出缓冲区长度',
            field: 'obl',
            sortable: true
        }, {
            title: '输出链长度',
            field: 'oll',
            sortable: true
        }, {
            title: '事件文件',
            field: 'events',
            sortable: true
        }, {
            title: '重定向',
            field: 'redir',
            sortable: true
        }],
        function (index, row) {
            var html = [];
        }
    ],
}
const oracleDiagnosticInfo = {
    fieldsProcesslist: [
        'oracle',
        ["All", "Active", "Others"],
        [{
            title: '',
            field: 'checkbox',
            checkbox: true
        }, {
            title: 'SESSION ID',
            field: 'SID',
            sortable: true
        }, {
            title: 'SERIAL#',
            field: 'SERIAL#',
            sortable: true
        }, {
            title: 'STATUS',
            field: 'STATUS',
            sortable: true
        }, {
            title: 'USER',
            field: 'USERNAME',
            sortable: true
        }, {
            title: 'MACHINE',
            field: 'MACHINE',
            sortable: true
        }, {
            title: 'SQL',
            field: 'SQL_TEXT',
            sortable: true,
            formatter: function (value, row, index) {
                if (row.SQL_TEXT.length > 60) {
                    let sql = row.SQL_TEXT.substr(0, 60) + '...';
                    return sql;
                } else {
                    return value
                }
            }
        }, {
            title: 'FULL SQL',
            field: 'SQL_FULLTEXT',
            visible: false,
            sortable: true
        }, {
            title: 'START TIME',
            field: 'SQL_EXEC_START',
            sortable: true
        }],
        function (index, row) {
            var html = [];
            $.each(row, function (key, value) {
                if (key === 'SQL_FULLTEXT') {
                    var sql = window.sqlFormatter.format(value);
                    //替换所有的换行符
                    sql = sql.replace(/\r\n/g, "<br>");
                    sql = sql.replace(/\n/g, "<br>");
                    //替换所有的空格
                    sql = sql.replace(/\s/g, "&nbsp;");
                    html.push('<span>' + sql + '</span>');
                }
            });
            return html.join('');
        }
    ],
}
