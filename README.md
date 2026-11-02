# OceanBase 生产排障 Skills

面向无源码的生产环境：读取运行时版本、租户、视图字段、实际参数及节点状态，再按证据排障。12 个技能均采用确认、定位、处置、验证四阶段。当前版本为 0.1.0，完成离线实现，集群实测与版本回归尚待运维环境验证。

| 症状域 | 入口 |
|---|---|
| 慢 SQL 与执行计划 | [oceanbase-query](oceanbase-query/SKILL.md) |
| 写入慢与写失败 | [oceanbase-write](oceanbase-write/SKILL.md) |
| 事务、行锁与死锁 | [oceanbase-transaction](oceanbase-transaction/SKILL.md) |
| 选主、日志与高可用 | [oceanbase-election-ha](oceanbase-election-ha/SKILL.md) |
| 冻结、合并与 Checkpoint | [oceanbase-compaction](oceanbase-compaction/SKILL.md) |
| 进程、内存、Crash 与 Hang | [oceanbase-observer](oceanbase-observer/SKILL.md) |
| 租户资源与排队 | [oceanbase-tenant-resource](oceanbase-tenant-resource/SKILL.md) |
| Tablet、LS 与热点 | [oceanbase-tablet](oceanbase-tablet/SKILL.md) |
| Unit 与副本迁移 | [oceanbase-balance](oceanbase-balance/SKILL.md) |
| DDL 与 Schema 一致性 | [oceanbase-ddl-schema](oceanbase-ddl-schema/SKILL.md) |
| 启动、部署与基础环境 | [oceanbase-deployment](oceanbase-deployment/SKILL.md) |
| CPU 与 IO 归因 | [oceanbase-cpu-io](oceanbase-cpu-io/SKILL.md) |

先读[命令与元数据](references/01-common-commands.md)、[版本和租户](references/03-tenant-and-version.md)、[错误码路由](references/02-error-code-routing.md)。级联分析见 [MemStore](guides/cascade-memstore-throttle.md) 与 [切主](guides/cascade-leader-switch.md)。

## 安装与离线校验

在本目录执行；将目标目录替换为需要安装的位置。所有技能、共享 references、guides 和脚本整体分发，引用不依赖源码仓库。已有目标默认拒绝覆盖，审阅后才使用 --force；不要将不相关文件放进包管理的 scripts/references/guides 子目录。

```bash safety=L0
bash scripts/install.sh --tool codex --target /tmp/ob-skills-preview
python3 scripts/skill_converter.py --sync
python3 scripts/safety_lint.py
python3 -m unittest discover -s tests -v
```

支持 codex、claude-code、cursor；JetBrains 仅生成可手工加载的 Markdown 包，不声称支持未知的 IDE 配置格式。源码分析仅用于作者开发时核实知识，不是生产运行依赖。

## 对原方案的调整

- 运行时元数据取代源码扫描：安装和查询生成都不依赖 src/。
- 版本由能力探测决定，不将源码表名存在解释为多版本兼容。
- 锁视图按现场 REQUEST/LMODE 与 holder 标识分析，去掉未验证的 need_wait 条件。
- 入口短文配按需 references；扩展信息放 metadata，以兼容技能 frontmatter。
- debug_sync/故障注入视为高风险，不能列作常规 L1 诊断。
- 不编造 30 个生产案例；候选根因与合成测试明确不代表实测。

[贡献与发布门禁](CONTRIBUTING.md)规定真实环境验收要求。安全扫描是作者检查工具，无法替代执行前对 SQL、权限与业务影响的判断。

## 诊断评测

[评测说明](evals/README.md)提供 20 个合成场景、盲测输入导出和人工审阅评分汇总。当前完成评测集与工具验证，尚未执行模型回放；脚本单元测试通过不代表模型诊断通过率。
