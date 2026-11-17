# 大模型对话助手 - 项目开发 Spec

## 1. 项目概述

开发一个基于 Python + Gradio 的大模型对话助手，支持多轮对话、会话管理、历史记录持久化，配置通过 .env 文件管理。

---

## 2. 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.10+ |
| 前端 UI | Gradio 5.x |
| 大模型调用 | OpenAI SDK（兼容 OpenAI 协议的接口） |
| 配置管理 | python-dotenv |
| 数据持久化 | SQLite（轻量，无需额外服务） |
| 会话管理 | 内存 + SQLite 持久化 |

---

## 3. 功能需求

### 3.1 核心对话功能
- [ ] 调用大模型接口进行流式/非流式多轮对话
- [ ] 支持用户输入和模型回复的展示
- [ ] 支持 Markdown 渲染（代码块、列表等）
- [ ] 对话上下文自动携带（发送历史消息给模型）

### 3.2 对话管理功能
- [ ] 左侧（或顶部）会话列表展示
- [ ] 新建对话：点击按钮创建新会话，自动切换
- [ ] 删除对话：支持删除单个会话，确认后移除
- [ ] 选择历史会话：点击列表项切换会话，加载历史消息
- [ ] 会话标题：首条用户消息自动生成标题（或默认"新对话"）
- [ ] 会话持久化：所有会话和消息保存到 SQLite

### 3.3 配置管理
- [ ] 使用 `.env` 文件管理大模型配置
- [ ] 支持配置项：API Key、Base URL、Model 名称、Temperature、Top P、Max Tokens
- [ ] 支持多模型配置切换（DeepSeek / 千问）
- [ ] 默认使用硅基流动（SiliconFlow）接口
- [ ] 应用启动时加载环境变量

---

## 4. 项目结构

```
chat-assistant/
├── .env                      # 大模型配置（用户自行配置）
├── .env.example              # 配置模板
├── .gitignore                # 忽略 .env、__pycache__、data/ 等
├── requirements.txt          # 依赖列表
├── main.py                   # 应用入口，启动 Gradio
├── config.py                 # 配置加载模块（读取 .env）
├── database.py               # SQLite 数据库操作封装
├── llm_client.py             # 大模型 API 调用封装
├── chat_service.py           # 对话业务逻辑（新建、删除、获取历史等）
├── ui/
│   └── app.py                # Gradio UI 定义与事件绑定
└── data/
    └── chat.db               # SQLite 数据库文件（运行时生成）
```

---

## 5. 模块设计

### 5.1 config.py — 配置加载
- 使用 `python-dotenv` 加载 `.env`
- 暴露配置类/字典：
  - 基础配置：`API_KEY`, `BASE_URL`, `MODEL`
  - 生成参数：`TEMPERATURE`, `TOP_P`, `MAX_TOKENS`
  - 多模型支持：`MODEL_PROVIDER`（deepseek / qwen），根据提供商自动映射 `BASE_URL` 和 `MODEL`
- 启动时校验必填项（如 API_KEY），缺失则报错提示
- 支持硅基流动默认配置：
  - DeepSeek：`https://api.siliconflow.cn/v1`，模型 `deepseek-ai/DeepSeek-V3`
  - Qwen：`https://api.siliconflow.cn/v1`，模型 `Qwen/Qwen3.5-27B`

### 5.2 database.py — 数据持久化
- 使用 `sqlite3` 标准库
- 初始化时创建表：
  - `conversations`：会话表（id, title, model_provider, model_name, created_at, updated_at）
  - `messages`：消息表（id, conversation_id, role, content, created_at）
- 封装 CRUD 方法：
  - `create_conversation(title, model_provider, model_name)` → conversation_id
  - `delete_conversation(conversation_id)`
  - `list_conversations()` → 按 updated_at 倒序
  - `get_messages(conversation_id)` → 按 created_at 正序
  - `add_message(conversation_id, role, content)`

### 5.3 llm_client.py — 大模型调用
- 使用 `openai` 库创建客户端
- 方法：`chat(messages, model, temperature, top_p, max_tokens, stream=True)`
- `messages` 格式：OpenAI 标准 `[{"role": "user", "content": "..."}, ...]`
- 支持流式返回（yield 方式），Gradio 中配合生成器使用
- 异常处理：网络超时、API 错误等，返回友好错误信息
- 支持根据 `model_provider` 自动选择对应的 `base_url` 和 `model_name`

### 5.4 chat_service.py — 业务逻辑
-  orchestration 层，串联 database + llm_client
- 方法：
  - `create_conversation(model_provider)` → 新建会话，返回 id
  - `delete_conversation(id)` → 删除会话及消息
  - `get_conversation_list()` → 获取会话列表（用于 UI 渲染）
  - `send_message(conversation_id, user_content, model_params)` → 保存用户消息 → 调用 LLM → 流式返回助手回复 → 保存助手消息
  - `get_conversation_history(conversation_id)` → 获取消息列表（用于切换会话时渲染）
  - `get_available_models()` → 返回支持的模型列表（deepseek、qwen）

### 5.5 ui/app.py — Gradio 界面
- **布局**：
  - 左侧：会话列表（`gr.DataFrame` 或 `gr.Markdown` + `gr.Button` 组合）+ 新建对话按钮
  - 右侧上方：模型选择下拉框（DeepSeek / Qwen）+ 参数设置折叠面板（Temperature、Top P、Max Tokens）
  - 右侧下方：Chatbot 组件 + 输入框
- **交互**：
  - 页面加载：渲染会话列表，默认选中模型
  - 点击"新建对话"：调用 `create_conversation()`，刷新列表，清空聊天区
  - 点击会话项：调用 `get_conversation_history()`，渲染到 Chatbot，恢复该会话使用的模型
  - 点击"删除"：确认后调用 `delete_conversation()`，刷新列表
  - 发送消息：调用 `send_message()` 流式更新 Chatbot，携带当前模型和参数
  - 参数调整：在折叠面板中实时调整，影响当前会话的下一次请求
- **状态管理**：使用 `gr.State` 保存当前 `conversation_id` 和 `model_params`

### 5.6 main.py — 入口
- 导入 `config`，校验配置
- 导入 `database`，初始化数据库
- 导入 `ui.app`，启动 Gradio（`demo.launch()`）

---

## 6. 数据模型

### conversations 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| title | TEXT | 会话标题 |
| model_provider | TEXT | 模型提供商（deepseek / qwen） |
| model_name | TEXT | 实际调用的模型名称 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 最后更新时间 |

### messages 表
| 字段 | 类型 | 说明 |
|------|------|
| id | INTEGER PK | 自增主键 |
| conversation_id | INTEGER FK | 关联会话 |
| role | TEXT | user / assistant |
| content | TEXT | 消息内容 |
| created_at | TIMESTAMP | 创建时间 |

---

## 7. .env 配置项

```env
# 大模型 API 配置（硅基流动）
LLM_API_KEY=your-siliconflow-api-key-here
LLM_BASE_URL=https://api.siliconflow.cn/v1

# 默认模型提供商：deepseek 或 qwen
LLM_PROVIDER=deepseek

# 可选：直接指定模型名称（若不指定则按提供商自动映射）
# LLM_MODEL=deepseek-ai/DeepSeek-V3

# 生成参数
LLM_TEMPERATURE=0.3
LLM_TOP_P=0.3
LLM_MAX_TOKENS=2048

```
---

## 8. 对话参数说明

| 参数 | 说明 | 取值范围 | 默认值 |
|------|------|----------|--------|
| **Temperature** | 采样温度，值越高输出越随机、越有创造性；值越低越确定、越保守 | 0.0 ~ 2.0 | 0.7 |
| **Top P** | 核采样，只从累积概率达到 top_p 的 token 中采样；与 Temperature 建议二选一调整 | 0.0 ~ 1.0 | 0.9 |
| **Max Tokens** | 模型生成的最大 token 数（包括输入和输出） | 1 ~ 8192 | 2048 |

> **建议**：Temperature 和 Top P 通常不建议同时大幅调整。日常对话推荐 Temperature=0.3；需要确定性回答时调低到 0.2 以下；需要创意发散时调高到 1.0 以上。

---

## 9. 模型映射配置

| 提供商 | 硅基流动 Base URL | 默认模型 |
|--------|-------------------|----------|
| DeepSeek | `https://api.siliconflow.cn/v1` | `deepseek-ai/DeepSeek-V3` |
| Qwen | `https://api.siliconflow.cn/v1` | `Qwen/Qwen3.5-27B` |

- 支持通过 `.env` 中的 `LLM_MODEL` 覆盖默认模型名称
- UI 中切换模型时，自动切换对应的 `model_name`，Base URL 保持不变（均为硅基流动）

---

## 10. 依赖列表 (requirements.txt)

```
gradio>=5.0.0
openai>=1.0.0
python-dotenv>=1.0.0
```

---

## 11. 开发顺序

1. **项目初始化**：创建目录结构、`.env.example`、`.gitignore`、`requirements.txt`
2. **配置模块**：实现 `config.py`，读取并校验 `.env`，支持多模型映射
3. **数据库模块**：实现 `database.py`，建表和基础 CRUD（增加 model_provider/model_name 字段）
4. **大模型客户端**：实现 `llm_client.py`，支持流式对话和多参数传递
5. **业务逻辑层**：实现 `chat_service.py`，串联各模块，支持模型切换
6. **UI 界面**：实现 `ui/app.py`，Gradio 布局（模型选择 + 参数面板 + 聊天区）和事件绑定
7. **入口文件**：`main.py` 整合启动
8. **测试验证**：多轮对话、模型切换、参数调整、新建/删除/切换会话、持久化验证

---

## 12. 验收标准

- [ ] 启动应用后，能正常加载配置并连接硅基流动大模型
- [ ] 可以进行多轮对话，模型能正确理解上下文
- [ ] 支持在 UI 中切换 DeepSeek / Qwen模型，切换后新对话使用选中模型
- [ ] 支持调整 Temperature、Top P、Max Tokens 参数
- [ ] 会话列表正确展示，支持新建、删除、切换
- [ ] 切换历史会话后，能正确加载并继续对话
- [ ] 重启应用后，历史会话和消息不丢失
- [ ] `.env` 配置变更后重启生效
