# 进程、内存、Crash 与 Hang：查询与判读

先按[公共流程](../../references/01-common-commands.md)探测，再执行针对本域的只读计划。工具位于包根目录 `scripts/metadata_probe.py`，仅支持 MySQL 模式自动采集。

```bash safety=L0
python3 scripts/metadata_probe.py --emit-sql --domain observer
python3 scripts/metadata_probe.py --plan capability.json --domain observer --tenant-id 1001 --start-us 0 --end-us 1
```

上面的租户和时间仅演示参数形式，必须换成已核实的目标租户和事故窗口（Unix epoch 微秒）；时间窗口上限一小时。计划只打印 SQL，不自动执行。生产查询前人工核对范围，业务租户与 sys 租户的可见性不同。

首选 `GV$OB_MEMORY`，所需字段为 `TENANT_ID`, `SVR_IP`, `SVR_PORT`, `CTX_NAME`, `MOD_NAME`, `HOLD`, `USED`。字段由 SHOW COLUMNS 返回，缺失时不推测同义字段。

补充 `GV$OB_THREAD`：先探测定义，再按已发现的对象字段过滤。工具不会自动对补充视图做全量 SELECT；由诊断者根据现场字段编写。

元数据探测失败时记录错误类别；无法访问数据库时转向已有监控、应用错误和节点日志，不以无数据补全根因。LIMIT 只限制返回行数，不保证底层分布式扫描成本；高压时使用已知对象定点采样，停止反复超时的采集。
