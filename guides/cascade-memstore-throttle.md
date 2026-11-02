# MemStore → 写限流 → 事务超时

从 [write](../oceanbase-write/SKILL.md) 获取同租户各节点 MemStore 两次样本和实际限流参数。水位持续增长、业务写延迟同步升高，只支持限流假设，仍需排除锁等待和日志盘问题。

若冻结次数增加但内存未释放，转 [compaction](../oceanbase-compaction/SKILL.md) 看同轮次未完成量和 tablet 进度，再关联设备延迟。冻结触发不等于落盘或内存回收完成。

如果事务超时，转 [transaction](../oceanbase-transaction/SKILL.md) 区分锁链与提交日志等待。减少应用非关键写并发需业务授权，按相同负载基线验证内存回落、队列减少、成功率恢复。不要直接关闭限流、删日志或强制结束未决事务。没有上述时序证据时保留为候选链，不宣称根因已确认。
