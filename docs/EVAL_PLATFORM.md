# 评测中台

## 1. 为什么需要评测中台

没有评测的 Agent 项目，最后都会变成“我试了几个问题，感觉还行”。

评测中台解决四件事：

1. 数据集版本化：同一批问题、同一批标准答案；
2. 评测任务化：一次运行对应一个 dataset version；
3. 指标可解释：确定性指标优先，LLM Judge 只做补充；
4. 回归门禁：每次改 Prompt、模型、检索参数都跑同一套集。

## 2. 数据模型

| 实体 | 说明 |
|---|---|
| EvalDataset | 数据集名称、benchmark、版本 |
| EvalCase | 单条问题、期望答案、相关文档、安全期望 |
| EvalRun | 一次评测任务，指向一个数据集版本 |
| EvalResult | 单条用例的输出、分数、是否通过、耗时 |

数据集不可变。要改题，就新建一个版本，不覆盖老版本。

## 3. 指标

### 中医药

- citation_accuracy：引用来源是否命中期望来源；
- refusal_correctness：该拒答时是否拒答；
- safety_pass：回答是否包含禁用断言（如“无需就医”）；
- faithfulness：回答是否被上下文支持，使用 Judge 加人工抽检。

### 零售

- formula_compliance：建议量是否与期望公式结果一致（允许容差）；
- tool_trace_accuracy：是否调用了必要工具；
- safety_pass：解释是否包含“保证不缺货”等违规承诺；
- explanation_helpfulness：人工抽检或 Judge。

## 4. 运行流程

~~~text
POST /v1/runs
  → 校验 dataset 属于当前租户
  → 创建 run（queued）
  → 后台执行
  → 逐条调用 Agent 接口
  → 计算指标
  → 写 eval_results
  → 汇总 metrics + pass_rate
  → run 状态 completed
~~~

生产环境把 asyncio.create_task 换成 Arq/Celery，任务落库，失败重试，避免 Pod 重启丢任务。

## 5. 回归门禁

建议阈值：

| 指标 | 门禁 |
|---|---|
| 引用准确率 | 不低于 0.85 |
| 拒答正确率 | 不低于 0.90 |
| 安全性 | 必须 1.00 |
| 补货公式一致率 | 必须 1.00 |
| 通过率 | 不低于基线 95% |

安全性是硬门禁，不能用平均分抵消。

## 6. LLM Judge 的边界

- Judge 不是标准答案，必须抽检；
- Judge Prompt 版本化；
- 记录 Judge 模型、温度、时间；
- 对高风险领域（医疗、金融）保留人工复核；
- 不允许用 Judge 分数替代确定性规则。

## 7. 与 Agent 的关系

Agent 返回 trace，包含检索上下文、候选文档、工具调用。评测平台用 trace 计算引用、工具、忠实度，而不是只看最终文本。

## 8. 模拟评测集

- tcm_golden.jsonl：5 条，覆盖药材、方剂、经典、拒答、急症边界；
- retail_golden.jsonl：4 条，覆盖正常补货、低样本、供应商无货、越权下单。

真实项目要扩到几百条，并按业务、难度、文档类型分层。
