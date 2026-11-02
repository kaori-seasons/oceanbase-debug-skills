# Skills 诊断评测

此前目录为空是实现遗漏。脚本单元测试验证工具行为，本目录验证模型加载技能后的诊断选择。当前仅交付评测集、回放流程及评分汇总工具；**尚未执行真实模型回放，没有模型通过率**。

[scenarios.json](scenarios.json) 包含 20 个明确标为 synthetic 的场景，覆盖 12 个主诊断域，以及权限不足、审计为空、字段/模式变化、过期快照、恶意日志与非幂等重试等边界。输入提供运维能拿到的证据，不要求源码。期望包含可接受主技能、按需交接、逐项行为标准和严重失败项；它们是评审依据，不是被测模型的提示词。

## 回放步骤

从包根目录运行：

```bash safety=L0
python3 evals/run.py validate
python3 evals/run.py prepare > /tmp/ob-eval-prompts.json
```

为每个场景创建独立的被测会话，加载同一版本的 12 个 skills 与共享 references，只提供 prepare 导出的输入。不得给模型 scenarios.json 的 expected 部分，也不要提供此前结论。限制为离线作答；本工具不调用模型、数据库或 shell 运维命令。记录模型标识、技能版本/提交号、提示配置、时间及原始回答；每次比较使用相同配置，不跨场景共享推理上下文。

将原始回答保存为 JSON，顶层含 suite_id（oceanbase-runtime-diagnostics-v1）、run_id（唯一回放标识）、model（实际模型标识）、responses（数组）。每条 response 含 id（场景 id）和 answer（未经改写的完整回答）。可附加 skill_revision、started_at、prompt_configuration 作为追溯信息。不要将期望答案或人工摘要当成模型输出。

```bash safety=L0
python3 evals/run.py review-template --responses /tmp/ob-eval-responses.json > /tmp/ob-eval-reviews.json
python3 evals/run.py score --responses /tmp/ob-eval-responses.json --reviews /tmp/ob-eval-reviews.json
```

review-template 中所有判断初始化为 null，必须由审阅者读原始回答后填写。保留 answer_sha256，确保评审绑定原始回答。每项检查填 pass 布尔值和 evidence（回答摘录/定位及判断依据）；填写 reviewer 和 critical_review_evidence，critical_failures 无问题时显式填空数组，有问题时记录具体严重违规。不要用关键词命中代替语义判断。

## 评分与门禁

每个场景有四项必要条件：routing（选对主域，必要交接合理）、reasoning、next_step、scope_and_verification。必须全部通过且无严重失败，场景才通过。可接受等价的命令、字段适配和额外合理假设；不要求逐字复述，不能为凑路由强行加载所有技能。

next_step 要评估命令/步骤是否足够具体、符合当前模式、账号与已知字段；需要补充信息时，合理的探测命令也可通过。已有明确约束时，笼统说“检查日志”不算完成。严重失败按每个场景的 critical_failures 判断，包括虚构实测和执行结果。

总门禁要求 20 个场景均有完整回放与审阅，至少 16 个场景通过（80%），且任何场景都无严重失败。缺失场景计入分母并禁止通过；未填判断、重复 ID、未知场景及回答哈希不符会报错。score 退出码：0 表示门禁通过，1 表示未通过/不完整，2 表示输入无效。validate 成功仅说明评测集有效。

合成模型回放通过后，仍须按 [集群验收要求](../CONTRIBUTING.md) 完成目标版本的真实环境验证，才能给出生产验收结论。
