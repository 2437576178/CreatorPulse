# 🤖 InferWatch — 模型区分与真实接入技术详解

> 配套文档：01_业务需求文档.md | 02_C4架构视图.md
> 本文档回答模型如何区分、不使用 Mock 数据如何真实接入 LLM API 等核心技术问题

---

## 1. 不同模型怎么区分？

### 1.1 只用 `model_name` 不够

`model_name` 是最核心的区分字段，但仅靠它不够。需要用一组字段联合标识一个"模型实例"：

```json
{
  "model": {
    "model_name": "gpt-4o-2024-08-06",
    "provider": "openai",
    "model_version": "2024-08-06",
    "model_size": "large",
    "is_self_hosted": false,
    "endpoint_url": "https://api.openai.com/v1/chat/completions"
  }
}
```

### 1.2 为什么需要这些额外字段？

| 场景 | 只用 `model_name` 的问题 | 解决方案 |
|------|--------------------------|----------|
| **同模型多版本** | `gpt-4o` 有 `2024-05-13` 和 `2024-08-06` 两个版本，后者便宜 50%，只用名字分不出 | 加上 `model_version` |
| **同模型多供应商** | Azure OpenAI 和 OpenAI 原生都叫 `gpt-4o`，价格相同但延迟不同（Azure 可能走专线） | 加上 `provider` + `endpoint_url` |
| **自建 vs API** | 自建 `qwen-72b` 按 GPU 时计费，阿里云 `qwen-turbo` 按 Token 计费，成本模型完全不同 | 加上 `is_self_hosted` |
| **模型大小切换** | `claude-sonnet` vs `claude-haiku`，后者便宜但能力弱，需要区分规格做推荐 | 加上 `model_size` |

### 1.3 各字段在系统各处的使用

```
┌─────────────────────────────────────────────────────────────┐
│  模拟数据生成时                                               │
│  model_name  覆盖 4 种: gpt-4o / gpt-4o-mini / claude-3.5 / qwen │
│  provider   覆盖 3 种: openai / anthropic / alibaba           │
│  model_version 每种 2 个版本模拟差异                           │
│  is_self_hosted: 80% false (API) / 20% true (自建)            │
├─────────────────────────────────────────────────────────────┤
│  Spark Streaming 实时分析时                                   │
│  RT-05 模型分布:     groupBy model_name                      │
│  RT-02 延迟分位值:   groupBy model_name + model_version      │
│  RT-04 成本速率:     groupBy model_name + provider           │
│  RT-03 错误率:       groupBy model_name + provider           │
├─────────────────────────────────────────────────────────────┤
│  SparkSQL 离线分析时                                         │
│  OF-09 供应商对比:   groupBy provider（跨模型对比）            │
│  OF-01 运营日报:     groupBy model_name + model_version      │
│  OF-02 成本归因:     groupBy model_name + business_line      │
├─────────────────────────────────────────────────────────────┤
│  Spark MLlib 推荐时                                          │
│  RC-01 模型选择:     输入特征含 model_size + is_self_hosted   │
│  RC-02 成本优化:     需要 provider + model_version 算精确成本  │
│  RC-06 供应商切换:    groupBy provider 做对比                 │
└─────────────────────────────────────────────────────────────┘
```

### 1.4 成本计算依赖完整模型标识

```scala
object CostCalculator {
  // (model_name, provider, model_version) → (input_price_per_1M_tokens, output_price_per_1M_tokens)
  val priceMap: Map[(String, String, String), (Double, Double)] = Map(
    ("gpt-4o",        "openai",    "2024-08-06") -> (2.50, 10.00),
    ("gpt-4o",        "openai",    "2024-05-13") -> (5.00, 15.00),  // 旧版贵一倍
    ("gpt-4o",        "azure",     "2024-08-06") -> (2.50, 10.00),  // Azure 同价但延迟不同
    ("gpt-4o-mini",   "openai",    "2024-07-18") -> (0.15, 0.60),
    ("claude-3.5",    "anthropic", "20241022")   -> (3.00, 15.00),
    ("qwen-turbo",    "alibaba",   "latest")     -> (0.30, 0.60),
    ("qwen-72b",      "self-host", "v0.1")       -> (0.05, 0.10),  // 自建按GPU时折算
  )

  def calcCost(modelName: String, provider: String, version: String,
               inputTokens: Int, outputTokens: Int): Double = {
    val (inputPrice, outputPrice) = priceMap((modelName, provider, version))
    (inputTokens / 1e6) * inputPrice + (outputTokens / 1e6) * outputPrice
  }
}
```

---

## 2. 不用 Mock 数据，如何真实接入？

### 2.1 核心问题

LLM API 调用本身不会主动发事件到 Kafka。需要一个机制在每次调用时把元数据"拦截"下来。

### 2.2 四种方案对比

| 方案 | 侵入性 | 可靠性 | 部署复杂度 | 适用场景 |
|------|:---:|:---:|:---:|------|
| 🥇 **SDK 包装器** | 低 | 高 | 低 | 自有代码调用 LLM |
| 🥈 **反向代理网关** | 零 | 最高 | 中 | 统一入口、不改代码 |
| 🥉 **Sidecar 边车** | 零 | 高 | 高 | K8s 环境 |
| 4 | **日志解析** | 零 | 低 | 已有日志系统 |

---

### 2.3 🥇 方案一：SDK 包装器（推荐）

**原理**：写一个轻量 Python 库，包装 OpenAI/Anthropic 等 SDK，在调用前后自动上报事件到 Kafka。

#### 用法（只需改一行 import）

```python
# 原来: from openai import OpenAI
# 改为:
from inferwatch_sdk import InferWatchOpenAI

client = InferWatchOpenAI(
    api_key="sk-...",
    app_id="customer-service-bot",
    kafka_brokers="node1:9092"
)

# 调用方式完全不变
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "你好"}]
)
# SDK 内部自动完成:
# 1. 记录 start_time
# 2. 计算 prompt_hash（SHA256，不存原文）
# 3. 调用真实 OpenAI API
# 4. 记录 end_time，计算 latency
# 5. 提取 tokens、cost 等
# 6. 异步发送事件到 Kafka（不阻塞主调用）
```

#### SDK 内部实现骨架

```python
import time, json, uuid, hashlib
from datetime import datetime
from kafka import KafkaProducer
from openai import OpenAI

class InferWatchOpenAI:
    def __init__(self, api_key, app_id, kafka_brokers,
                 business_line="default", scenario="general"):
        self._client = OpenAI(api_key=api_key)
        self._app_id = app_id
        self._business_line = business_line
        self._scenario = scenario
        self._producer = KafkaProducer(
            bootstrap_servers=kafka_brokers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            linger_ms=10,            # 10ms 批量发送，不阻塞
            compression_type='gzip'
        )

    @property
    def chat(self):
        return self._ChatProxy(self)

    class _ChatProxy:
        def __init__(self, parent):
            self.completions = self._CompletionsProxy(parent)

        class _CompletionsProxy:
            def __init__(self, parent):
                self._p = parent

            def create(self, **kwargs):
                # 构建请求事件（不含 prompt 原文）
                messages = kwargs.get("messages", [])
                event = {
                    "event_id": f"evt-{uuid.uuid4().hex[:12]}",
                    "trace_id": f"trace-{uuid.uuid4().hex}",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "app": {
                        "app_id": self._p._app_id,
                        "business_line": self._p._business_line,
                        "scenario": self._p._scenario
                    },
                    "request": {
                        "endpoint": "/v1/chat/completions",
                        "prompt_hash": hashlib.sha256(
                            json.dumps(messages, ensure_ascii=False).encode()
                        ).hexdigest()[:16],
                        "prompt_length_chars": len(json.dumps(messages, ensure_ascii=False)),
                        "max_tokens": kwargs.get("max_tokens", 2048),
                        "temperature": kwargs.get("temperature", 1.0),
                        "stream": kwargs.get("stream", False)
                    },
                    "model": {
                        "model_name": kwargs.get("model", "unknown"),
                        "provider": "openai",
                        "is_self_hosted": False
                    }
                }

                start = time.time()
                try:
                    response = self._p._client.chat.completions.create(**kwargs)
                    total_latency = (time.time() - start) * 1000

                    event["response"] = {
                        "status": "success",
                        "http_status_code": 200,
                        "finish_reason": response.choices[0].finish_reason,
                        "input_tokens": response.usage.prompt_tokens,
                        "output_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                        "total_latency_ms": total_latency,
                        "cost_usd": self._calc_cost(
                            kwargs.get("model"),
                            response.usage.prompt_tokens,
                            response.usage.completion_tokens
                        ),
                        "retry_count": 0
                    }
                except Exception as e:
                    event["response"] = {
                        "status": "error",
                        "total_latency_ms": (time.time() - start) * 1000
                    }
                    event["error"] = {
                        "error_type": type(e).__name__,
                        "error_message": str(e)[:200]
                    }

                # 异步发送到 Kafka
                self._p._producer.send("llm_api_calls", value=event)
                return response

            def _calc_cost(self, model, input_tokens, output_tokens):
                prices = {
                    "gpt-4o": (2.50, 10.00),
                    "gpt-4o-mini": (0.15, 0.60),
                }
                in_price, out_price = prices.get(model, (0, 0))
                return (input_tokens / 1e6) * in_price + (output_tokens / 1e6) * out_price
```

---

### 2.4 🥈 方案二：反向代理网关（零侵入）

**原理**：部署一个轻量代理服务，所有 LLM API 调用先经过它，它转发到真实 API 并记录事件。

```
应用代码（只需改 base_url）:

  client = OpenAI(
      api_key="sk-...",
      base_url="http://inferwatch-proxy:8080/v1"   // ← 指向代理
  )
  # 其他代码完全不变
```

```
架构:

各业务线应用 ──→ InferWatch Proxy (Flask) ──→ 真实 LLM API
                      │
                      └──→ Kafka (node1:9092)
                           llm_api_calls topic
```

#### 代理核心代码骨架

```python
from flask import Flask, request, Response
import requests, time, json, uuid, hashlib

app = Flask(__name__)
producer = KafkaProducer(bootstrap_servers='node1:9092', ...)

# 路由表：请求路径前缀 → 真实后端
ROUTE_MAP = {
    "openai":    "https://api.openai.com",
    "anthropic": "https://api.anthropic.com",
    "qwen":      "http://qwen-cluster:8000",
}

@app.route('/<provider>/v1/chat/completions', methods=['POST'])
def proxy_chat(provider):
    target_url = f"{ROUTE_MAP[provider]}/v1/chat/completions"
    req_body = request.get_json()
    messages = req_body.get("messages", [])

    # 构建事件（不存 prompt 原文）
    event = {
        "event_id": f"evt-{uuid.uuid4().hex[:12]}",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "app": {"app_id": request.headers.get("X-App-ID", "unknown")},
        "model": {
            "model_name": req_body.get("model"),
            "provider": provider,
            "is_self_hosted": provider in ("qwen",),  # qwen 标记为自建
        },
        "request": {
            "prompt_hash": hashlib.sha256(
                json.dumps(messages, ensure_ascii=False).encode()
            ).hexdigest()[:16],
            "prompt_length_chars": len(json.dumps(messages, ensure_ascii=False)),
            "max_tokens": req_body.get("max_tokens"),
            "temperature": req_body.get("temperature"),
            "stream": req_body.get("stream", False),
        }
    }

    start_time = time.time()
    try:
        resp = requests.post(
            target_url,
            headers={
                "Authorization": request.headers.get("Authorization"),
                "Content-Type": "application/json"
            },
            json=req_body, timeout=120
        )
        total_latency = (time.time() - start_time) * 1000
        resp_body = resp.json()

        event["response"] = {
            "status": "success",
            "http_status_code": resp.status_code,
            "input_tokens": resp_body.get("usage", {}).get("prompt_tokens", 0),
            "output_tokens": resp_body.get("usage", {}).get("completion_tokens", 0),
            "total_latency_ms": total_latency,
        }
    except Exception as e:
        event["response"] = {"status": "error"}
        event["error"] = {"error_type": type(e).__name__}

    # 异步发送到 Kafka
    producer.send("llm_api_calls", value=event)

    return Response(
        json.dumps(resp_body),
        status=resp.status_code,
        content_type="application/json"
    )
```

---

### 2.5 方案选择建议

| 你的情况 | 推荐方案 |
|----------|----------|
| 自己能改应用代码 | 🥇 **SDK 包装器**，一行 import 搞定 |
| 不能改代码、有统一网关 | 🥈 **反向代理**，零侵入 |
| K8s + Service Mesh | 🥉 **Sidecar**，Istio/Envoy 扩展 |
| 已有 Nginx 日志 | 4️⃣ **日志解析**，从 access log 提取 |

### 2.6 本项目推荐双模支持

```
轻量模式（开发/小团队）:
  应用 → InferWatch SDK → Kafka → Spark → MySQL

网关模式（生产/多团队）:
  应用 → InferWatch Proxy → 真实 LLM API
                ↓
              Kafka → Spark → MySQL
```

**关键设计**：模拟数据阶段用 Shell 脚本写 Kafka，真实接入阶段只需把 Shell 脚本替换为 SDK 或 Proxy，**下游的 Kafka → Spark Streaming → MySQL → Flask → Vue 全链路完全不变**。

---

> 📌 本文件回答了 InferWatch 的两个核心技术问题，与业务需求文档和 C4 架构配合阅读。
