# 慢 SQL 与执行计划：查询与判读

先按[公共流程](../../references/01-common-commands.md)探测，再执行针对本域的只读计划。工具位于包根目录 `scripts/metadata_probe.py`，仅支持 MySQL 模式自动采集。

```bash safety=L0
python3 scripts/metadata_probe.py --emit-sql --domain query
python3 scripts/metadata_probe.py --plan capability.json --domain query --tenant-id 1001 --start-us 0 --end-us 1
```

上面的租户和时间仅演示参数形式，必须换成已核实的目标租户和事故窗口（Unix epoch 微秒）；时间窗口上限一小时。计划只打印 SQL，不自动执行。生产查询前人工核对范围，业务租户与 sys 租户的可见性不同。

首选 `GV$OB_SQL_AUDIT`，所需字段为 `TENANT_ID`, `TRACE_ID`, `SQL_ID`, `PLAN_ID`, `REQUEST_TIME`, `ELAPSED_TIME`, `QUEUE_TIME`, `GET_PLAN_TIME`, `EXECUTE_TIME`, `APPLICATION_WAIT_TIME`, `USER_IO_WAIT_TIME`, `RETURN_ROWS`。字段由 SHOW COLUMNS 返回，缺失时不推测同义字段。

补充 `GV$OB_PLAN_CACHE_PLAN_STAT`：先探测定义，再按已发现的对象字段过滤。工具不会自动对补充视图做全量 SELECT；由诊断者根据现场字段编写。

按同一 SQL_ID/PLAN_ID 对比同类请求。耗时分项存在包含/重叠关系，不能简单相加或用 EXECUTE_TIME 减等待时间当作 CPU 时间。多节点审计记录不一定等于客户端请求数。默认不导出 QUERY_SQL、绑定值、客户端 IP。

元数据探测失败时记录错误类别；无法访问数据库时转向已有监控、应用错误和节点日志，不以无数据补全根因。LIMIT 只限制返回行数，不保证底层分布式扫描成本；高压时使用已知对象定点采样，停止反复超时的采集。
