# 整体架构

## 1. 设计目标

这套参考实现要回答面试里最常见的三个问题：

1. Agent 怎么和业务系统对接？
2. 数据质量和评测怎么做，而不是只靠“感觉”？
3. 企业里两个 Agent 怎么共享中台，而不是各建一套烟囱？

## 2. 分层

~~~text
接入层      API Gateway / OIDC / 限流 / WAF
应用层      岐黄智库 Agent       零售订货 Agent
编排层      LangGraph             LangGraph + Go order-service
中台层      数据中台             评测中台
基础设施    PostgreSQL Redis Qdrant OpenSearch Neo4j MinIO Airflow
~~~

### 接入层

- 统一 JWT 鉴权，网关注入 X-Tenant-Id；
- 每个请求带 X-Request-Id，日志、指标、Tracing 共用；
- 对外只暴露 /v1，内部接口使用 /internal + 服务令牌；
- 限流、WAF、审计在网关层完成，业务服务只做兜底。

### 应用层

两个 Agent 是独立部署单元，不共享进程和数据库表：

- 岐黄智库 Agent：只读知识库、知识图谱和安全规则；
- 零售订货 Agent：只读特征、调用订单服务，不直接写订单表。

### 中台层

- 数据中台：数据目录、质量门禁、特征服务、血缘；
- 评测中台：评测集版本、评测任务、指标、Judge、回归报告。

### 基础设施

| 组件 | 用途 | 备注 |
|---|---|---|
| PostgreSQL | 元数据、任务、评测、特征快照 | 生产用托管实例 |
| Redis | 缓存、限流、短期会话 | 不存唯一事实 |
| Qdrant | 稠密向量检索 | 可替换为 Milvus |
| OpenSearch | BM25 与日志检索 | 中文分词需 IK 插件 |
| Neo4j | 中医药知识图谱 | 只做扩展，不做唯一证据 |
| MinIO/S3 | 原始文档、评测集、报告 | 开启版本控制 |
| Airflow | 批处理编排 | DAG 只做编排，转换在 dbt |
| dbt | 零售数仓与特征模型 | 模型有测试和血缘 |

## 3. 两个关键调用链

### 中医药问答

~~~text
用户问题
  → JWT / tenant
  → classify（意图）
  → normalize（术语归一化）
  → retrieve（BM25 + 向量 + RRF）
  → graph_expand（知识图谱）
  → safety_precheck（急症/处方/特殊人群）
  → generate（LLM）
  → verify（引用越界、禁用断言）
  → finalize（免责声明）
~~~

### 零售订货

~~~text
用户问题
  → parse（门店/SKU/日期）
  → load_features（数据中台特征服务）
  → forecast（确定性预测）
  → supply（Go 订单服务查供货）
  → calculate（补货公式 + 约束）
  → explain（LLM 只解释）
  → 人工确认
  → Go 订单服务幂等下单
~~~

## 4. 为什么共享中台

数据口径、权限和评测标准必须一致。比如“缺货率”只允许有一个定义；“引用准确率”只允许有一套评测脚本。共享中台让两个 Agent 的变更都能进入同一套回归门禁。

## 5. 技术选型

| 领域 | 选型 | 理由 |
|---|---|---|
| Agent 编排 | LangGraph | 状态、条件边、checkpoint、可观测 |
| API | FastAPI + Pydantic v2 | 类型契约、OpenAPI、生态成熟 |
| 数据访问 | SQLAlchemy 2 + asyncpg | 异步、类型友好 |
| 批处理 | Airflow | 企业普及度高、运维成熟 |
| 转换 | dbt | SQL 可测试、血缘清晰 |
| 质量 | Pandera | 轻量、可单元测试 |
| 向量 | Qdrant | 过滤、部署简单 |
| 检索 | OpenSearch | BM25、日志同栈 |
| 图 | Neo4j | 关系扩展、Cypher |
| 评测 | Ragas/DeepEval 兼容层 + 自研指标 | 指标可解释，避免黑盒 |
| 观测 | OpenTelemetry + Prometheus + Langfuse | 指标、链路、LLM trace |
| 订单 | Go + MySQL | 强类型、事务、并发和外部接口稳定 |

## 6. 可靠性设计

- 所有下游调用设置超时；
- 重试只用于幂等操作或带幂等键的操作；
- 数据质量不通过时阻断发布，不静默降级；
- 评测失败阻断 CI 合并；
- 订单写入使用本地事务 + 唯一键 + Outbox；
- Agent 有最大步数和递归上限，防止死循环；
- 医疗场景安全规则优先于模型输出。

## 7. 已知取舍

1. 共享中台增加部署复杂度，小团队可以先用模块化单体。
2. 评测平台的 LLM Judge 有偏差，必须保留人工抽检。
3. 知识图谱只做辅助，不把图关系当作直接医学证据。
4. 模拟数据只能验证流程，不能证明真实业务效果。
