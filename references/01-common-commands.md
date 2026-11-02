# 生产运行时元数据与命令

本页所有数据库命令均用于 MySQL 模式。先确认连接租户和账号权限。数据库工具只执行身份查询和 SHOW COLUMNS，不读取源码，不修改数据库，也不自动执行排障 SELECT。执行诊断需使用已授权的连接。没有连接信息时先打印命令交运维执行，不猜测地址或凭据。

## 1. 确认身份、版本、模式

```sql safety=L0 context=current-account
SELECT VERSION() AS version, CURRENT_USER() AS account, DATABASE() AS current_database;
SHOW VARIABLES LIKE 'ob_compatibility_mode';
SHOW VARIABLES LIKE 'ob_query_timeout';
SHOW VARIABLES LIKE 'ob_trx_timeout';
```

用户名文本不是 tenant_id 的可靠映射。请由运维核实业务租户 ID；有权限时可探测并查询租户清单。不要默认 sys 连接能绕过所有视图的租户过滤。

```sql safety=L0 context=sys-authorized
SHOW COLUMNS FROM oceanbase.DBA_OB_TENANTS;
SELECT TENANT_ID, TENANT_NAME FROM oceanbase.DBA_OB_TENANTS LIMIT 20;
```

只有 SHOW COLUMNS 确认列存在后才执行下一条 SELECT。

## 2. 探测目标诊断面的字段

```sql safety=L0 context=current-account
SHOW COLUMNS FROM oceanbase.GV$OB_SQL_AUDIT;
SHOW COLUMNS FROM oceanbase.GV$OB_LOCKS;
SHOW COLUMNS FROM oceanbase.GV$OB_MEMSTORE;
```

逐条运行，只探测当前症状相关视图。SHOW COLUMNS 可确认解析和权限是否允许，不能证明实际查询开销很低。错误分类：表不存在→版本/模式差异；权限不足→换用已经授权的账号或请运维代查；连接失败→部署与网络；超时→停止扩大采样。空结果是独立状态，不能证明全局正常。

## 3. 可选自动采集

以下从安装包根目录运行。替换路径、地址和用户名；凭据写在已有 MySQL defaults 文件中（权限 0600），不要放入命令行或报告。该文件支持标准客户端 TLS 配置；沿用生产要求的证书验证，不降低连接安全设置。输出包含版本、连接身份等元数据，保留在受控目录并脱敏后分享。

```bash safety=L0
python3 scripts/metadata_probe.py --emit-sql --domain transaction
python3 scripts/metadata_probe.py --collect --domain transaction --defaults-extra-file /secure/ob.cnf --host db.example.invalid --port 2881 --user diagnostic@tenant > capability.json
python3 scripts/check_virtual_tables.py --metadata capability.json
python3 scripts/metadata_probe.py --plan capability.json --domain transaction --tenant-id 1001
```

每条元数据命令客户端等待上限 10 秒；超时后停止本轮采集。终止客户端不保证服务端立即取消，勿密集重试。部分失败仍输出快照并以非零状态退出。工具生成的 SELECT 需人工复核租户、连接、窗口和字段语义，再执行。快照仅代表采集时账号可见能力，版本或账号变更后重新探测。

## 4. 参数与日志

```sql safety=L0 context=current-account
SHOW PARAMETERS LIKE 'freeze_trigger_percentage';
SHOW PARAMETERS LIKE 'writing_throttling_trigger_percentage';
SHOW PARAMETERS LIKE 'memstore_limit_percentage';
SHOW PARAMETERS LIKE 'log_disk_utilization_threshold';
SHOW PARAMETERS LIKE 'log_disk_utilization_limit_threshold';
```

以返回的实际值、租户和服务器范围为准，不用源码默认值代替运行配置。参数不存在或不可见时保留缺口。

在已授权的 observer 所在 Linux 主机上，核实 PID、部署路径和挂载点；这些命令不适用于本地 macOS 的生产状态推断：

```bash safety=L0
ps -eo pid,comm,etime,%cpu,%mem
free -m
df -h
df -i
vmstat 1 5
iostat -xz 1 5
```

iostat 可能未安装；使用现有监控替代，不自动安装软件。vmstat/iostat 首份输出通常为启动以来平均值，分析后续区间。日志从已核实路径的指定事故窗口取少量行，按 trace_id、事务 ID 或 LS 标识关联；日志格式和路径以部署为准。不递归扫描整个数据盘。core、SQL 文本、绑定值与日志均可能含敏感信息。

## 5. 审计导出分析

```bash safety=L0
python3 scripts/analyze_sql_audit.py audit.csv --metric elapsed_time --top 20
```

接受带表头的 CSV/TSV（多行 SQL 需正确引用），不解析 mysql ASCII 表格。ELAPSED_TIME 等时间字段按微秒，REQUEST_MEMORY_USED 按字节。输出仅包含记录序号和数值，避免默认泄露 SQL/客户标识；序号指 CSV 记录，含多行字段时不等于物理文件行号。TOP-N 只描述导出样本，不代表完整事故。

官方语法依据：[SHOW COLUMNS](https://en.oceanbase.com/docs/common-oceanbase-database-10000000001377912)、[参数与变量查询](https://oceanbase.github.io/docs/user_manual/quick_starts/en-US/chapter_02_deploy_oceanbase_database/set-parameters)。现场版本和实际权限仍需先探测。
