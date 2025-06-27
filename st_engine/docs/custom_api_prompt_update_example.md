# 自定义API的Prompt更新功能使用示例

## 功能概述

为了让自定义API能够使用与`chat_completions`接口相同的压测数据，我们实现了动态更新payload中prompt字段的功能。

## 配置示例

### 1. 简单字段映射

如果您的自定义API使用简单的字段来接收prompt：

```json
{
  "field_mapping": {
    "prompt": "input",
    "content": "output.text",
    "stream_prefix": "data:",
    "stop_flag": "[DONE]"
  },
  "request_payload": {
    "model": "custom-model",
    "input": "这里的内容会被自动替换",
    "temperature": 0.7,
    "max_tokens": 1000
  }
}
```

在压测过程中，`input`字段的值会被自动替换为当前的prompt数据。

### 2. 嵌套字段映射

如果您的API使用嵌套结构：

```json
{
  "field_mapping": {
    "prompt": "messages.0.content",
    "content": "choices.0.message.content",
    "stream_prefix": "data:",
    "stop_flag": "[DONE]"
  },
  "request_payload": {
    "model": "custom-model",
    "messages": [
      {
        "role": "user",
        "content": "这里的内容会被自动替换"
      }
    ],
    "temperature": 0.7
  }
}
```

在这个例子中，`messages[0].content`字段会被自动更新。

### 3. 复杂嵌套结构

对于更复杂的API结构：

```json
{
  "field_mapping": {
    "prompt": "request.query.text",
    "content": "response.data.generated_text",
    "stream_prefix": "event:",
    "stop_flag": "[COMPLETE]"
  },
  "request_payload": {
    "request": {
      "query": {
        "text": "占位符文本",
        "language": "zh"
      },
      "parameters": {
        "max_length": 1000,
        "temperature": 0.8
      }
    }
  }
}
```

## 多模态数据支持

系统能够自动处理多模态数据，提取其中的文本部分：

```python
# 如果prompt_data是字符串
prompt_data = "请描述人工智能的发展历史"
# 直接使用

# 如果prompt_data是字典（多模态）
prompt_data = {
    "prompt": "请描述这张图片",
    "image_base64": "base64_encoded_image_data"
}
# 只提取prompt字段的值用于更新payload
```

## 压测配置示例

在启动Locust压测时，完整的配置如下：

```bash
locust -f locustfile.py \
    --task-id="custom_api_test" \
    --api_path="/api/v1/generate" \
    --field_mapping='{"prompt": "input", "content": "output"}' \
    --request_payload='{"model": "test", "input": "placeholder", "temperature": 0.7}' \
    --stream_mode=True \
    --users=10 \
    --spawn-rate=2 \
    --run-time=60s
```

## 行为说明

1. **prompt数据获取**: 系统会从prompt队列中获取下一个prompt数据，与`chat_completions`接口使用相同的数据源
2. **字段映射**: 根据`field_mapping.prompt`配置的路径，定位到payload中需要更新的字段
3. **动态更新**: 将获取的prompt数据设置到指定字段
4. **类型处理**: 自动处理字符串和多模态数据类型
5. **错误容错**: 如果字段映射失败，会记录警告但不会中断压测

## 注意事项

- 确保`field_mapping.prompt`路径在`request_payload`中存在
- 支持嵌套字段路径，使用点号分隔（如`messages.0.content`）
- 支持数组索引访问（如`items.0.field`）
- 如果没有配置`field_mapping.prompt`，将使用原始payload而不进行更新
