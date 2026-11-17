# 企业级 Agent 双项目套件

面向 AI Agent / RAG / 数据智能岗位的**企业级参考实现**，包含两个业务 Agent 和两套共享中台：

| 模块 | 目录 | 说明 |
|---|---|---|
| 岐黄智库 Agent | apps/tcm-knowledge-agent | 中医药知识库问答、辨证要点检索、经典引用、用药安全护栏 |
| 零售订货 Agent | apps/retail-ordering-agent | 门店补货建议、需求预测、供应商供货、人工确认、幂等下单 |
| 数据中台 | platforms/data-platform | 数据目录、数据质量、特征服务、血缘、Airflow DAG、dbt 模型 |
| 评测中台 | platforms/eval-platform | 评测集版本、评测任务、自动指标、LLM Judge、回归报告 |
| 订单服务 | services/order-service | Go 订单服务、幂等键、MySQL 事务、Outbox、供应商适配 |
| 公共库 | packages/common | 配置、日志、JWT 鉴权、租户上下文、错误契约、OpenTelemetry |

## 为什么是一个仓库

两个 Agent 共享同一套数据中台和评测中台，这是企业中台化的常见做法：

- 数据中台统一管理数据目录、质量规则、特征口径和血缘；
- 评测中台统一管理评测集、评测任务和回归报告；
- 两个 Agent 只负责自己的业务编排和领域逻辑；
- 订单服务独立部署，专门处理交易和外部供应商接口。

相比给每个 Agent 复制一套平台，共享中台更容易保证口径一致、权限一致、评测标准一致。

## 本地启动

~~~bash
cp .env.example .env
make bootstrap
make infra-up
make data
make dev
~~~

默认端口：

| 服务 | 端口 |
|---|---|
| 数据中台 | 8001 |
| 评测中台 | 8002 |
| 岐黄智库 Agent | 8011 |
| 零售订货 Agent | 8012 |
| 订单服务 Go | 8020 |

本地开发可用 Docker Compose 启动 PostgreSQL、Redis、Qdrant、OpenSearch、MinIO。生产环境建议使用托管数据库、对象存储和独立的向量检索集群。

## 一条完整演示链路

### 中医药知识库

1. 数据中台执行 tcm_ingestion DAG，解析经典文本、药典条目、用药禁忌；
2. 质量规则校验必填字段、重复文档、禁忌字段；
3. Agent 收到问题后进行术语归一化、混合检索、知识图谱扩展、安全预检；
4. 生成带经典出处的回答；
5. 评测中台对回答做引用准确率、忠实度、安全性评测。

### 零售订货

1. 数据中台执行 retail_ingestion DAG，生成销售、库存、促销、供应商数据；
2. dbt 构建门店-SKU 日汇总和补货特征表；
3. 零售 Agent 读取特征、预测需求、计算建议订货量；
4. 调用 Go 订单服务查询供应商供货；
5. 店长确认后创建订单，幂等键和 MySQL 唯一索引兜底；
6. 评测中台对建议量、工具调用、解释质量做回归评测。

## 设计原则

1. **LLM 只做理解和表达，数字与写操作交给确定性代码。**
2. **所有检索必须带租户与权限过滤，权限前置。**
3. **所有外部调用必须有超时、重试、熔断和可观测性。**
4. **所有写接口必须支持幂等，所有状态变更必须可审计。**
5. **评测不是演示，必须有版本化数据集、固定指标和回归门禁。**
6. **代码注释解释“为什么”，不是复述“是什么”。**

## 文档

- docs/README.md：文档索引
- docs/ARCHITECTURE.md：整体架构与调用链
- docs/DATA_PLATFORM.md：数据中台设计
- docs/EVAL_PLATFORM.md：评测中台设计
- docs/TCM_AGENT.md：中医药 Agent 设计
- docs/RETAIL_AGENT.md：零售 Agent 设计
- docs/OPERATIONS.md：部署、监控、故障处理
- docs/adr/0001-shared-platform.md：为什么共享中台

## 面试手册

- [企业级 Agent 双项目面试全流程手册（PDF）](docs/企业级Agent双项目面试全流程手册.pdf)
- 工作区根目录保留 docx / md 版本，方便继续修改。

## 说明

本项目是**企业级参考实现**，不是某家公司的生产系统。外部模型、向量库、搜索引擎、医药数据和供应商接口需要按实际环境配置；医药相关回答必须由执业医师/药师复核，不能用于诊断和处方。