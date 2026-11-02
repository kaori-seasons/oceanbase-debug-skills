# 错误入口

先确认日志中的 OB 内部错误码，客户端可能返回不同 MySQL/Oracle 映射码。错误码只决定首个验证方向，不能直接给出根因。

| 内部码 | 首选技能 | 必须补充的证据 |
|---|---|---|
| -4013 / -4080 | [observer](../oceanbase-observer/SKILL.md) | 租户、模块内存与 MemStore 趋势 |
| -6003 / -6005 / -6006 | [transaction](../oceanbase-transaction/SKILL.md) | 等待者、持锁者、事务与等待持续时间 |
| -6210 / -6212 | [transaction](../oceanbase-transaction/SKILL.md) | 事务/语句超时类型、运行参数、锁/日志进度 |
| -4213 / -4217 | [compaction](../oceanbase-compaction/SKILL.md) | 已有合并轮次和当前是否允许冻结 |
| -4103 | [tablet](../oceanbase-tablet/SKILL.md) | 具体对象、节点和校验日志 |

-6005 是内部尝试行锁冲突线索，不能直接等同已经发生死锁；-6210 不能单凭错误文本建议增大超时。未知错误保留原始码、消息、版本与时间，查现场版本官方错误手册。
