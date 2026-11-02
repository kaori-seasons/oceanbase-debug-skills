---
{
  "name": "oceanbase-ddl-schema",
  "description": "Use when OceanBase has DDL stuck, schema version mismatch, index build. 处理DDL 与 Schema 一致性，基于运行时元数据、只读 SQL 与运维命令排障。",
  "metadata": {
    "version": "0.1.0",
    "applies_to": "OceanBase 4.x/5.x capability-gated; MySQL collector; Oracle manual",
    "validation": "offline-tested; live-cluster validation pending",
    "keywords": "DDL 与 Schema 一致性; DDL stuck, schema version mismatch, index build"
  }
}
---

# DDL 与 Schema 一致性

先读[租户与版本前提](../references/03-tenant-and-version.md)。生产环境无需源码；使用数据库实际返回的视图与列。当前包尚未完成真实集群回归，不得声称所有版本都支持示例。

## Phase 1 — 确认范围

记录事故时间与时区、连接入口、租户、模式、节点、业务症状与最近变更。先获取[运行时能力快照](../references/01-common-commands.md)，再读本技能的[查询与判读](references/queries.md)。区分无权限、不存在、连接失败和查询结果为空。错误码需要注明 OB 内部码还是客户端映射码。

## Metric Taxonomy

| 层次 | 观测 | 判读限制 |
|---|---|---|
| 业务 | 错误率、吞吐、p95/p99 | 与同负载基线比较 |
| 数据库 | `GV$OB_SERVER_SCHEMA_INFO` | 先探测字段，按租户/节点/时间限定 |
| 关联面 | `DBA_OB_ROOTSERVICE_EVENT_HISTORY` | 只能证明可见范围内的状态 |
| OS/日志 | 同时段 CPU、IO、进程与日志 | 对齐节点和时区，相关性不等于因果 |

## Phase 2 — 缩小根因

| 候选原因 | 确认条件 | 下一步与交接 |
|---|---|---|
| DDL 等待 | 任务阶段长期不变且存在事务或锁依赖 | 保留 DDL 任务与会话标识，先追踪阻塞事务；[transaction](../oceanbase-transaction/SKILL.md) |
| Schema 刷新滞后 | 同租户不同服务器版本差异持续存在并伴随请求错误 | 关联 schema 刷新日志与网络状态；瞬时版本差不是根因；[election-ha](../oceanbase-election-ha/SKILL.md) |
| 构建阶段资源不足 | 索引构建时间线与合并/IO 压力一致 | 确认任务阶段后评估业务低峰调度；不要反复提交相同 DDL；[compaction](../oceanbase-compaction/SKILL.md) |

对同一对象取至少两次带时间戳的样本，确认趋势；选择一个最能区分当前假设的观测，不循环扫描全库。SQL_AUDIT 是有限保留的数据，事故记录缺失不能当作没有异常。

## Phase 3 — 按证据处置

- **DDL 等待**：只有在“任务阶段长期不变且存在事务或锁依赖”成立时推进。保留 DDL 任务与会话标识，先追踪阻塞事务。同时记录能推翻该判断的反例，验证失败则回到 Phase 2。
- **Schema 刷新滞后**：只有在“同租户不同服务器版本差异持续存在并伴随请求错误”成立时推进。关联 schema 刷新日志与网络状态；瞬时版本差不是根因。同时记录能推翻该判断的反例，验证失败则回到 Phase 2。
- **构建阶段资源不足**：只有在“索引构建时间线与合并/IO 压力一致”成立时推进。确认任务阶段后评估业务低峰调度；不要反复提交相同 DDL。同时记录能推翻该判断的反例，验证失败则回到 Phase 2。

涉及参数、会话终止、重启或副本动作时，执行前写明对象、影响、原值、回退和观察窗口，并确认已有授权涵盖该动作。不得从诊断授权推导变更授权。L3 操作只说明风险与升级路径，不生成可复制命令。详见[处置边界](references/actions.md)。

## Phase 4 — 验证恢复

在可比负载下检查业务错误率、吞吐和延迟，并复采同一租户/节点/对象的异常指标。建议覆盖多个采样周期和至少一个业务事务周期；只恢复进程或告警消失不足以关闭事件。输出：证据、支持/排除的假设、已执行动作、未执行建议、恢复状态、仍缺信息。

## 因果链

- DDL 等待 → 任务阶段长期不变且存在事务或锁依赖 → 业务退化；断点：保留 DDL 任务与会话标识，先追踪阻塞事务。用前后同范围样本验证，不能将链条当成已确认事实。
- Schema 刷新滞后 → 同租户不同服务器版本差异持续存在并伴随请求错误 → 业务退化；断点：关联 schema 刷新日志与网络状态；瞬时版本差不是根因。用前后同范围样本验证，不能将链条当成已确认事实。
- 构建阶段资源不足 → 索引构建时间线与合并/IO 压力一致 → 业务退化；断点：确认任务阶段后评估业务低峰调度；不要反复提交相同 DDL。用前后同范围样本验证，不能将链条当成已确认事实。

## 交接

携带已脱敏的版本、租户模式、时间窗口、节点、SQL/事务/LS/tablet 标识、能力快照和最近两个样本；缺失信息明确标注。真实案例须经脱敏复盘再入库，当前根因表是诊断假设，不是已验证事故。
