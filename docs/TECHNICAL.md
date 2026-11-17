# 大模型对话助手 - 技术架构文档

## 目录
1. [系统架构概览](#1-系统架构概览)
2. [模块详细设计](#2-模块详细设计)
3. [关键技术方案](#3-关键技术方案)
4. [数据持久化](#4-数据持久化)
5. [错误处理](#5-错误处理)
6. [已知限制](#6-已知限制)
7. [扩展方向](#7-扩展方向)

## 1. 系统架构概览

### 1.1 架构设计

本项目采用 **分层架构**，自底向上分为四层：

```
┌─────────────────────────────────────────────────────────┐
│                    表现层 (Presentation)                  │
│  ┌─────────────────────────────────────────────────┐    │
│  │  ui/app.py - Gradio Web UI                      │    │
│  │  - 会话管理面板（新建、删除、刷新）               │    │
│  │  - 聊天交互面板（消息输入、流式输出）             │    │
│  │  - 参数控制面板（模型、角色、输出格式、参数）     │    │
│  └─────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────┤
│                    业务层 (Business Logic)                │
│  ┌─────────────────────────────────────────────────┐    │
│  │  chat_service.py - ChatService                  │    │
│  │  - 会话生命周期管理                              │    │
│  │  - 消息处理流程（构建上下文 → 调用模型 → 保存）   │    │
│  │  - 上下文压缩（长对话自动总结）                   │    │
│  │  - 幻觉检测（事实核查）                          │    │
│  │  - JSON 格式验证                                 │    │
│  └─────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────┤
│                    数据访问层 (Data Access)               │
│  ┌──────────────────────┐  ┌──────────────────────┐    │
│  │  database.py         │  │  config.py           │    │
│  │  - SQLite CRUD       │  │  - 环境变量读取       │    │
│  │  - 会话/消息持久化    │  │  - 模型映射管理       │    │
│  │  - 外键级联删除       │  │  - 配置验证           │    │
│  └──────────────────────┘  └──────────────────────┘    │
├─────────────────────────────────────────────────────────┤
│                    基础设施层 (Infrastructure)            │
│  ┌──────────────────────┐  ┌──────────────────────┐    │
│  │  llm_client.py       │  │  .env 配置文件        │    │
│  │  - OpenAI SDK 封装    │  │  - API Key           │    │
│  │  - 流式响应处理       │  │  - Base URL          │    │
│  │  - 多模型提供商支持    │  │  - 模型参数           │    │
│  └──────────────────────┘  └──────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### 1.2 技术栈

| 层级 | 技术选型 | 版本 | 说明 |
|------|---------|------|------|
| 编程语言 | Python | 3.10+ | 后端开发语言 |
| Web UI | Gradio | 5.x | 快速构建 Web 界面 |
| LLM SDK | openai | 1.x | 兼容 OpenAI 协议的模型调用 |
| 配置管理 | python-dotenv | 1.x | 环境变量加载 |
| 数据库 | SQLite | 3.x | 轻量级关系型数据库 |

### 1.3 数据流

```
用户输入 → Gradio UI → ChatService.send_message()
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
              database   llm_client   提示词模板
              (保存消息)  (调用模型)   (构建上下文)
                    │         │         │
                    ▼         ▼         ▼
              SQLite DB  ←  流式响应  →  上下文压缩/幻觉检测
                    │
                    ▼
              Gradio UI (流式渲染)
```

---

## 2. 模块详细设计

### 2.1 配置模块 (config.py)

**职责**：集中管理所有配置项，提供模型映射和参数验证。

#### 2.1.1 核心类

| 类名 | 说明 |
|------|------|
| `Config` | 配置类，封装所有大模型相关配置 |

#### 2.1.2 模型映射表

```python
MODEL_MAPPING = {
    "deepseek": {
        "base_url": "https://api.siliconflow.cn/v1",
        "model_name": "deepseek-ai/DeepSeek-V3"
    },
    "qwen": {
        "base_url": "https://api.siliconflow.cn/v1",
        "model_name": "Qwen/Qwen2.5-72B-Instruct"
    }
}
```

#### 2.1.3 关键方法

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `get_model_info(provider)` | provider: 模型提供商 | dict: {base_url, model_name} | 获取指定模型配置 |
| `validate()` | 无 | list: 错误信息列表 | 验证配置有效性 |
| `get_default_params()` | 无 | dict: 默认参数 | 获取默认生成参数 |
| `get_available_models()` | 无 | list: 提供商列表 | 获取所有可用模型 |

#### 2.1.4 配置加载流程

```
.env 文件 → python-dotenv 加载 → os.getenv() 读取 → Config 类属性
```

---

### 2.2 数据库模块 (database.py)

**职责**：提供 SQLite 数据库的 CRUD 操作，管理会话和消息的持久化存储。

#### 2.2.1 数据库表结构

**会话表 (conversations)**

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 会话唯一标识 |
| title | TEXT | NOT NULL DEFAULT '新对话' | 会话标题 |
| model_provider | TEXT | NOT NULL | 模型提供商（deepseek/qwen） |
| model_name | TEXT | NOT NULL | 使用的模型名称 |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |
| updated_at | TIMESTAMP | NOT NULL | 最后更新时间 |

**消息表 (messages)**

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 消息唯一标识 |
| conversation_id | INTEGER | NOT NULL, FOREIGN KEY | 关联的会话ID |
| role | TEXT | NOT NULL | 角色（user/assistant/system） |
| content | TEXT | NOT NULL | 消息内容 |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |

**外键约束**：`ON DELETE CASCADE` - 删除会话时自动删除关联消息。

#### 2.2.2 核心函数

| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `init_database()` | 无 | 无 | 初始化数据库，创建表结构 |
| `create_conversation(title, provider, name)` | 标题、提供商、模型名 | int: 会话ID | 创建新会话（含标题去重） |
| `delete_conversation(conversation_id)` | 会话ID | 无 | 删除会话及关联消息 |
| `list_conversations()` | 无 | list: 会话列表 | 获取所有会话（按更新时间倒序） |
| `get_messages(conversation_id)` | 会话ID | list: 消息列表 | 获取会话所有消息 |
| `add_message(conversation_id, role, content)` | 会话ID、角色、内容 | 无 | 添加消息并更新会话时间 |
| `update_conversation_title(conversation_id, title)` | 会话ID、新标题 | 无 | 更新会话标题 |
| `update_conversation_model(conversation_id, provider, name)` | 会话ID、提供商、模型名 | 无 | 更新会话模型配置 |
| `get_conversation_by_id(conversation_id)` | 会话ID | dict: 会话详情 | 根据ID获取会话 |

#### 2.2.3 会话标题去重逻辑

```python
if title != "新对话":
    # 检查是否存在相同标题，若有则添加数字后缀
    while True:
        count = SELECT COUNT(*) FROM conversations WHERE title = ?
        if count == 0: break
        counter += 1
        title = f"{original_title} ({counter})"
```

---

### 2.3 大模型客户端 (llm_client.py)

**职责**：封装 OpenAI SDK，提供统一的模型调用接口，支持多模型提供商和流式响应。

#### 2.3.1 核心类

| 类名 | 说明 |
|------|------|
| `LLMClient` | 大模型客户端，管理多个模型客户端实例 |

#### 2.3.2 关键方法

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `create_client_for_provider(provider)` | provider: 模型提供商 | OpenAI 客户端实例 | 创建指定模型的客户端 |
| `chat(messages, model, **params)` | 消息列表、模型名、参数 | generator: 流式响应 | 调用模型获取流式响应 |

#### 2.3.3 流式响应处理

```python
def chat(self, messages, model, **params):
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,  # 启用流式响应
        **params
    )
    for chunk in response:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

---

### 2.4 业务逻辑模块 (chat_service.py)

**职责**：整合数据库和 LLM 客户端，实现完整的对话业务流程。

#### 2.4.1 核心类

| 类名 | 说明 |
|------|------|
| `ChatService` | 对话服务类，封装所有对话相关业务逻辑 |

#### 2.4.2 角色模板系统

```python
ROLE_TEMPLATES = {
    "default": {
        "name": "默认助手",
        "description": "友好的通用对话助手",
        "system_prompt": "你是一位友好的助手..."
    },
    "tech": { ... },      # 技术专家
    "teacher": { ... },   # 辅导老师
    "writer": { ... },    # 文案作家
    "analyst": { ... }    # 数据分析专家
}
```

#### 2.4.3 输出格式配置

```python
OUTPUT_FORMATS = {
    "text": "自然语言",
    "json": "JSON 格式",
    "list": "清单格式"
}
```

#### 2.4.4 核心方法

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `create_conversation(provider, role)` | 提供商、角色 | int: 会话ID | 创建新会话并添加系统提示词 |
| `delete_conversation(conversation_id)` | 会话ID | 无 | 删除会话 |
| `send_message(conversation_id, user_content, ...)` | 会话ID、用户内容、参数等 | generator: 流式响应 | 发送消息并获取响应（核心方法） |
| `get_conversation_history(conversation_id)` | 会话ID | list: 消息列表 | 获取会话历史 |
| `build_prompt(role, output_format, user_content)` | 角色、输出格式、用户内容 | str: 系统提示词 | 构建系统提示词 |
| `compress_context(messages, max_tokens, model_provider)` | 消息列表、token限制、模型提供商 | list: 压缩后消息 | 上下文压缩 |
| `detect_hallucination(response, messages, model_provider)` | 响应、消息、模型提供商 | tuple: (是否检测到, 原因) | 幻觉检测 |
| `validate_json_output(response)` | 模型响应 | tuple: (是否有效, 错误信息) | JSON 格式验证 |
| `get_available_models()` | 无 | list: 模型列表 | 获取可用模型 |
| `get_available_roles()` | 无 | dict: 角色映射 | 获取可用角色 |
| `get_available_output_formats()` | 无 | dict: 格式映射 | 获取输出格式 |
| `get_conversation_by_id(conversation_id)` | 会话ID | dict: 会话详情 | 获取会话详情 |
| `get_role_info(role_key)` | 角色键名 | dict: 角色信息 | 获取角色模板详情 |

#### 2.4.5 send_message 完整流程

```
1. 验证会话存在
   ↓
2. 如果提供了新模型提供商，更新会话模型配置
   ↓
3. 保存用户消息到数据库
   ↓
4. 获取当前会话所有消息
   ↓
5. 构建系统提示词（角色 + 输出格式）
   ↓
6. 构建发送给模型的消息列表
   ↓
7. 长对话时进行上下文压缩（>15条消息）
   ↓
8. 打印调试日志（模型、参数）
   ↓
9. 流式调用模型获取响应
   ↓
10. JSON格式输出时验证格式
    ↓
11. 幻觉检测
    ↓
12. 保存助手响应到数据库
    ↓
13. 首次消息时更新会话标题
```

#### 2.4.6 上下文压缩算法

```python
def compress_context(self, messages, max_tokens=3000, model_provider=None):
    # 消息 ≤ 3 条，不压缩
    if len(messages) <= 3:
        return messages
    
    # 保留最近 10 条消息
    recent_messages = messages[-10:]
    
    # 提取历史消息生成总结提示词
    conversation_text = "\n".join([f"{m['role']}: {m['content'][:200]}" for m in messages[:-10]])
    
    # 调用模型生成总结（≤200字）
    summary = call_llm(summary_prompt)
    
    # 返回：系统提示词 + 总结 + 最近消息
    return [system_prompt, {"role": "assistant", "content": summary}, *recent_messages]
```

#### 2.4.7 幻觉检测逻辑

```python
def detect_hallucination(self, response, messages, model_provider=None):
    # 短内容跳过检测（<50字）
    if len(response) < 50:
        return False, "内容较短，跳过检测"
    
    # 构建事实核查提示词
    fact_check_prompt = f"""请分析以下AI回答是否可能包含幻觉..."""
    
    # 调用模型检测（temperature=0.1 保证一致性）
    result = call_llm(fact_check_prompt, temperature=0.1)
    
    # 解析检测结果
    if result.startswith("是"):
        return True, result
    return False, None
```

#### 2.4.8 JSON 格式验证

```python
def validate_json_output(self, response):
    cleaned_response = response.strip()
    
    # 1. 尝试直接解析
    try:
        json.loads(cleaned_response)
        return True, None
    except json.JSONDecodeError:
        pass
    
    # 2. 尝试从响应中提取 JSON（正则匹配 { } 或 [ ]）
    json_match = re.search(r'(\{.*\}|\[.*\])', cleaned_response, re.DOTALL)
    if json_match:
        extracted_json = json_match.group(1)
        try:
            json.loads(extracted_json)
            return True, None
        except json.JSONDecodeError as e:
            return False, f"提取的 JSON 解析失败: {str(e)}"
    
    # 3. 返回原始错误
    return False, str(e)
```

---

### 2.5 UI 模块 (ui/app.py)

**职责**：使用 Gradio 构建 Web 界面，实现用户交互和状态管理。

#### 2.5.1 界面布局

```
┌─────────────────────────────────────────────────────────┐
│                    Gradio App                           │
├──────────────────────┬──────────────────────────────────┤
│  左侧：会话管理面板   │  右侧：聊天交互面板              │
│  (scale=1)           │  (scale=3)                       │
│                      │                                  │
│  - 会话下拉框         │  - Chatbot（消息展示）           │
│  - 新建对话按钮       │  - 输入框                        │
│  - 刷新列表按钮       │  - 发送按钮                      │
│  - 删除会话按钮       │                                  │
│  - 角色选择           │  参数控制面板                    │
│  - 角色描述           │  - 模型选择                      │
│                      │  - 输出格式选择                  │
│                      │  - Temperature 滑块              │
│                      │  - Top P 滑块                    │
│                      │  - Max Tokens 滑块               │
└──────────────────────┴──────────────────────────────────┘
```

#### 2.5.2 核心函数

| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `load_conversation_list()` | 无 | tuple: (choices, value) | 加载会话列表 |
| `load_conversation_history(conversation_id)` | 会话ID | list: 消息列表 | 加载会话历史 |
| `create_new_conversation(model_provider, role)` | 模型提供商、角色 | tuple: (chatbot, dropdown) | 创建新会话 |
| `delete_selected_conversation(conversation_id)` | 会话ID | tuple: (chatbot, dropdown) | 删除选中会话 |
| `send_message(message, history, ...)` | 消息、历史、参数等 | generator: (input, chatbot) | 发送消息（流式） |
| `get_role_description(role_key)` | 角色键名 | str: 角色描述 | 获取角色描述 |
| `build_app()` | 无 | gr.Blocks | 构建 Gradio 应用 |

#### 2.5.3 全局状态

```python
current_conversation_id = None  # 当前选中的会话ID
```

#### 2.5.4 事件绑定

| 事件 | 触发函数 | 输入 | 输出 | 说明 |
|------|---------|------|------|------|
| `conversation_dropdown.change` | `load_conversation_history` | dropdown | chatbot | 切换会话加载历史 |
| `new_btn.click` | `create_new_conversation` | model, role | chatbot, dropdown | 新建会话 |
| `refresh_btn.click` | `refresh_list` | 无 | dropdown | 刷新会话列表 |
| `delete_btn.click` | `delete_selected_conversation` | dropdown | chatbot, dropdown | 删除会话 |
| `send_btn.click` | `send_message` | 所有输入参数 | input, chatbot | 发送消息 |
| `msg_input.submit` | `send_message` | 所有输入参数 | input, chatbot | 回车发送 |
| `role_dropdown.change` | `get_role_description` | dropdown | markdown | 更新角色描述 |

#### 2.5.5 Gradio 5.x 兼容性处理

```python
# Column 使用 scale 而非 width
with gr.Column(scale=1):
    ...

# Chatbot 使用 type="messages"
chatbot = gr.Chatbot(type="messages", ...)

# DataFrame 不使用 height 参数
df = gr.DataFrame(...)

# Dropdown 使用 allow_custom_value=True
dropdown = gr.Dropdown(..., allow_custom_value=True)

# 使用 gr.update() 更新组件
return gr.update(choices=choices, value=value)
```

---

### 2.6 应用入口 (main.py)

**职责**：应用启动入口，负责配置验证、数据库初始化和 UI 启动。

#### 2.6.1 启动流程

```
1. 验证配置（Config.validate()）
   - 检查 API Key 是否配置
   - 检查模型提供商是否有效
   - 检查参数范围是否合法
   ↓
2. 初始化数据库（init_database()）
   - 创建 data 目录
   - 创建 conversations 表
   - 创建 messages 表
   ↓
3. 构建并启动 Gradio 应用（build_app().launch()）
   - server_name: 0.0.0.0（允许外部访问）
   - server_port: 7860
   - share: False（不生成共享链接）
   - debug: True（启用调试模式）
```

---

## 3. 关键技术方案

### 3.1 流式响应实现

**原理**：利用 OpenAI SDK 的 `stream=True` 参数，逐 chunk 接收模型响应，通过 Python generator 实现流式输出。

```python
def chat(self, messages, model, **params):
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        **params
    )
    for chunk in response:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

**Gradio 端处理**：
```python
for chunk in chat_service.send_message(...):
    response = chunk["content"]
    new_history = history + [{"role": "user", "content": message}, 
                             {"role": "assistant", "content": response}]
    yield "", new_history
```

### 3.2 多模型支持

**设计模式**：策略模式 + 工厂模式

```
Config.MODEL_MAPPING
       │
       ├── deepseek → base_url + model_name
       └── qwen     → base_url + model_name
              │
              ▼
       LLMClient.create_client_for_provider(provider)
              │
              ▼
       OpenAI(api_key, base_url) 客户端实例
```

### 3.3 会话命名策略

| 阶段 | 命名规则 | 实现位置 |
|------|---------|---------|
| 新建会话 | "新对话"（不添加数字后缀） | database.py: create_conversation() |
| 首次消息 | 提取前 10 字，超长加 "..." | chat_service.py: send_message() |
| 标题重复 | 添加数字后缀 (1), (2)... | chat_service.py: send_message() |

### 3.4 上下文压缩策略

```
消息数量 ≤ 3  → 不压缩
消息数量 4-15 → 保留所有消息
消息数量 > 15 → 总结历史 + 保留最近 10 条
```

### 3.5 幻觉检测策略

```
响应长度 < 50 字 → 跳过检测
响应长度 ≥ 50 字 → 调用模型检测（temperature=0.1）
```

---

## 4. 数据持久化

### 4.1 数据库文件

- **路径**：`data/chat.db`
- **类型**：SQLite 3
- **自动创建**：应用启动时自动创建目录和表

### 4.2 表关系

```
conversations (1) ────< (N) messages
       │                      │
       │ id                   │ conversation_id (FK)
       │                      │
       └── ON DELETE CASCADE ──┘
```

### 4.3 事务管理

所有写操作使用独立事务：
```python
conn = sqlite3.connect(DATABASE_PATH)
cursor = conn.cursor()
# 执行 SQL
conn.commit()
conn.close()
```

---

## 5. 错误处理

### 5.1 配置验证

```python
errors = Config.validate()
if errors:
    print("配置验证失败:")
    for error in errors:
        print(f"  - {error}")
    return
```

### 5.2 会话不存在处理

```python
conversation = get_conversation_by_id(conversation_id)
if not conversation:
    raise ValueError("会话不存在")
```

### 5.3 JSON 格式错误处理

```python
is_valid, error = self.validate_json_output(full_response)
if not is_valid:
    yield {"content": f"JSON格式错误: {error}\n\n原始响应:\n{full_response}", ...}
    return
```

---

## 6. 已知限制

| 限制 | 说明 | 影响 |
|------|------|------|
| Gradio Dropdown 动态更新 | Gradio 5.x 存在 bug，流式输出中无法可靠更新下拉框 | 需要手动点击"刷新列表"按钮 |
| SQLite 并发 | SQLite 不支持高并发写操作 | 单用户场景足够，多用户需改用 PostgreSQL |
| 上下文窗口 | 依赖模型的上下文窗口大小 | 长对话需依赖上下文压缩功能 |
| 幻觉检测准确性 | 基于大模型自身判断，非绝对准确 | 仅供参考，不能作为事实依据 |

---

## 7. 扩展方向

| 方向 | 说明 |
|------|------|
| 多用户支持 | 添加用户表，实现多用户隔离 |
| 向量数据库 | 集成 RAG 能力，支持知识库检索 |
| 模型微调 | 支持自定义模型和微调参数 |
| 插件系统 | 支持工具调用（搜索、计算器等） |
| 部署优化 | Docker 容器化，支持生产环境部署 |
