# 数据中台

## 1. 定位

数据中台不是“一个大数据库”，而是四件事：

1. 数据目录：有什么数据、谁负责、什么敏感级别；
2. 数据质量：能不能用、什么时候阻断；
3. 特征服务：Agent 在线拿到的特征口径固定、可追溯；
4. 血缘：一个指标从哪张表、哪个 DAG、哪段 SQL 来的。

## 2. 核心实体

| 实体 | 说明 |
|---|---|
| DataAsset | 文档语料、表、特征视图、知识图谱 |
| QualityRun | 一次质量检查及报告 |
| FeatureSnapshot | 门店-SKU-日期的特征快照 |
| LineageEdge | 上游资产、下游资产、作业、转换 SQL |
| DataMetric | 缺货率、周转、文档覆盖率等指标 |

## 3. 数据分层

### 中医药

~~~text
raw/tcm/documents.jsonl     原始文档
staging_tcm_documents       清洗、去重、术语归一
tcm_chunks                  分块、向量化
tcm_entities                药材、方剂、经典实体
tcm_entity_relations        知识图谱关系
~~~

### 零售

~~~text
raw/retail/fact_sales.csv           原始销售
raw/retail/inventory_snapshot.csv   库存快照
stg_sales / stg_inventory           dbt staging
fct_store_sku_daily                 门店-SKU-日汇总
feature_replenishment_input         在线补货特征
~~~

## 4. 质量门禁

### 中医药文档

- doc_id 唯一；
- title、category、source、content 必填；
- content 长度不低于 80；
- 来源加标题不能重复；
- 禁忌字段不能为空（药材/方剂类）；
- 敏感级别必须标记。

### 零售销售

- qty 大于等于 0；
- promo_flag 只能是 0 或 1；
- 门店、SKU、日期唯一；
- 日期可解析；
- 库存不能为负；
- 数据日期覆盖最近 N 天。

质量检查失败时：

1. DAG 失败，不发布新特征；
2. 告警到数据平台值班；
3. 阻断依赖该特征的 Agent 发布；
4. 在评测平台记录数据版本，避免坏数据跑出好成绩。

## 5. 特征服务

Agent 不查原始表，只调用：

~~~http
POST /v1/features/query
{
  "feature_view": "feature_replenishment_input",
  "store_id": "S01",
  "sku": "SKU-0001",
  "business_date": "2026-12-07T00:00:00Z"
}
~~~

返回 payload，包含 avg_qty_7d、avg_qty_28d、on_hand、in_transit、case_pack、moq 等。

特征快照有版本和新鲜度检查。超过 feature_max_staleness_hours 返回 404，Agent 必须降级，不能拿过期数据算补货。

## 6. 编排

Airflow DAG：

- tcm_ingestion：校验文档，dbt 构建元数据；
- retail_ingestion：校验销售和库存，dbt 构建 mart，再跑 dbt test。

Airflow 不写业务 SQL，业务 SQL 在 dbt。DAG 只负责调度、重试、告警和依赖。

## 7. 血缘

每次 dbt 运行和特征发布写入 LineageEdge：

~~~text
fact_sales -> fct_store_sku_daily -> feature_replenishment_input
~~~

面试时可以说：血缘的价值不是画图，而是出问题时能在 5 分钟内定位“哪个上游变更影响了哪个 Agent”。

## 8. API 与权限

- 资产目录：用户 JWT + tenant；
- 质量任务、特征查询：内部服务令牌；
- 原始数据下载：单独审批，不走 Agent 服务；
- 敏感字段（患者、员工、供应商价格）按列脱敏。

## 9. 模拟数据

本地运行：

~~~bash
make data
~~~

生成：

- 中医药文档 15 条以上，含经典、药材、方剂、指南、安全边界；
- 零售 8 家门店、60 个 SKU、120 天销售、库存、促销、供应商报价。

数据是合成的，仅用于流程和评测演示。
