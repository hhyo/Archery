const pgsql_diagnostic = {
    pgFieldsProcesslist: [
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
    ]
}
