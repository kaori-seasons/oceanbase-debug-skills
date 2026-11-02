# 切主 → 日志/回放积压 → 读写超时

从 [election-ha](../oceanbase-election-ha/SKILL.md) 按同租户同 LS 记录角色、提案和日志位置，至少两次采样；同步获取节点心跳、网络和时间同步证据。正常切主本身不能证明故障。

若进度差持续扩大，转 [cpu-io](../oceanbase-cpu-io/SKILL.md) 与 [transaction](../oceanbase-transaction/SKILL.md)，分别排除日志写盘瓶颈及事务依赖。区分实际数据路径与客户端路由延迟；OBProxy 自身故障不在本包覆盖范围。

优先恢复网络/磁盘等已确认的外因。成员变更、强制切主和副本删除均不能仅凭当前角色推导。验证需要多数派与副本同步状态稳定、同 LS 进度差收敛、业务读写成功，并记录观察窗口。
