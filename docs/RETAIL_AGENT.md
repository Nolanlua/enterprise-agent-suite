# 零售订货 Agent

## 1. 业务目标

面向连锁门店店长和区域运营，解决：

- 订货靠经验，容易缺货或压货；
- 供应商可供货信息不透明；
- 补货计算口径不统一；
- 下单重复、难以审计。

Agent 给出建议，人确认，订单服务落单。

## 2. 边界

LLM 只做两件事：

1. 理解门店、SKU、日期等意图；
2. 把已经算好的结果解释成人话。

不做：

- 预测数字；
- 补货公式；
- MOQ/箱规/预算计算；
- 直接写订单。

## 3. 工作流

~~~text
parse_intent → load_features → forecast → supply → calculate → explain
~~~

### parse_intent

正则优先识别 S01、SKU-0001、覆盖天数。识别不到时返回明确错误，不猜。

### load_features

调用数据中台特征服务：

- avg_qty_7d、avg_qty_28d；
- on_hand、in_transit、safety_stock；
- case_pack、moq、shelf_life_days；
- unit_price。

特征过期或缺失时返回错误，不拿旧数据计算。

### forecast

~~~text
baseline = avg_qty_7d 优先，否则 avg_qty_28d
trend = clamp((avg_7 + 0.5) / (avg_28 + 0.5), 0.8, 1.3)
daily = baseline × trend × promo_factor
confidence = 基于波动率和促销打折
~~~

### supply

调用 Go 订单服务查询供应商可供货：

- 供应商编码、供应商 SKU；
- 可供货量、价格、MOQ、箱规、交期。

无供货时返回空列表，补货结果标记 supplier_unavailable。

### calculate

~~~text
forecast_demand = daily_qty × coverage_days
safety_stock = daily_qty × safety_days
raw_gap = forecast_demand + safety_stock - on_hand - in_transit

按箱规向上取整
不低于 MOQ
不超过可供货量
不超过最大订货量
不超过预算
标记保质期风险、低置信度风险
~~~

所有约束调整都写入 reasons 和 risks。

### explain

LLM 只能解释，不能改数字。代码校验回答中是否包含建议量，不包含就用模板兜底。

## 4. 确认与下单

~~~http
POST /v1/ordering/confirm
Idempotency-Key: order:S01:SKU-0001:20261207-001
~~~

流程：

1. 校验门店权限；
2. 调用 Go 订单服务；
3. 订单服务先查幂等键；
4. 调供应商下单；
5. 本地事务写订单、明细、幂等响应、Outbox；
6. 唯一键冲突时回查并返回已有结果。

## 5. 订单服务

- Go 标准库 net/http；
- MySQL 事务 + 唯一索引；
- Idempotency-Key；
- Outbox 事件；
- 供应商适配器，5xx/网络重试，4xx 不重试；
- 健康检查、优雅关闭。

## 6. 指标

- 建议采纳率；
- 缺货率；
- 库存周转；
- 预测 WAPE；
- 单店决策时长；
- 订单幂等命中率。

## 7. 已知限制

1. 预测是统计基线，不是生产级时序模型；
2. 促销系数目前在模拟数据里，真实系统要接促销中台；
3. 供应商成功、本地失败的不一致需要 Outbox 补偿 Worker；
4. 没有真实门店 PoS 数据；
5. 人工确认目前是 API 层，生产要有工作台和审计。
