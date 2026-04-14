# 携程智能体项目

## 项目简介

基于 LangGraph 构建的旅行领域 AI 智能体，模拟携程场景，支持多轮对话与工具调用，能够完成机票/酒店查询、行程规划等任务。

### 工作流程

整体采用主助理 + 四个专业子助理的多 Agent 架构，由 `fetch_user_info` 预加载用户信息后进入主助理，主助理负责查询与任务分发，写操作委派给对应子助理执行，敏感工具调用前中断等待用户确认。

```
用户输入
   │
   ▼
┌──────────────────┐
│  fetch_user_info  │  预加载乘客航班信息 → 写入 State.user_info
└──────────────────┘
   │ route_to_workflow（条件路由）
   ▼
┌──────────────────────┐ ◄─────────────────── leave_skill
│   primary_assistant   │   （子助理完成后返回）
└──────────────────────┘
   │
   ├─ 查询/搜索 ──► primary_assistant_tools ──► primary_assistant
   │
   ├─ 航班改签/退票 ──► enter_update_flight ──► update_flight
   │                                               ├─ update_flight_safe_tools
   │                                               └─ update_flight_sensitive_tools  [⚠️ 中断确认]
   │
   ├─ 租车预订 ──► enter_book_car_rental ──► book_car_rental
   │                                               ├─ book_car_rental_safe_tools
   │                                               └─ book_car_rental_sensitive_tools [⚠️ 中断确认]
   │
   ├─ 酒店预订 ──► enter_book_hotel ──► book_hotel
   │                                               ├─ book_hotel_safe_tools
   │                                               └─ book_hotel_sensitive_tools      [⚠️ 中断确认]
   │
   ├─ 旅游推荐 ──► enter_book_excursion ──► book_excursion
   │                                               ├─ book_excursion_safe_tools
   │                                               └─ book_excursion_sensitive_tools  [⚠️ 中断确认]
   │
   └─ 纯文本回复 ──► END
```

**各环节说明：**

1. **入口** — 提供两种运行模式：
   - `graph_chat/graph_gradio.py`（Gradio Web UI）：浏览器交互式聊天界面，用户输入通过 Chatbot 组件展示
   - `graph_chat/workflow.py`（命令行）：终端逐轮对话，以 `stream_mode="values"` 流式执行图
   
   两种模式均支持敏感工具中断确认（输入 `y` 继续，否则回传拒绝原因）。

2. **fetch_user_info 节点** — 图启动后首先执行，调用 `fetch_user_flight_information` 拉取当前乘客航班信息，写入 `State.user_info`，供主助理系统提示直接使用。

3. **primary_assistant 节点** (`graph_chat/assistant.py`) — 主助理，负责回答查询类问题（搜索航班、查政策）；若涉及预订/改签/退订，通过委派工具（`ToFlightBookingAssistant` 等）将任务交给对应子助理。

4. **子助理节点** (`graph_chat/agent_assistant.py`) — 航班、租车、酒店、旅游各有独立子助理，内部按工具类型路由：只读操作走 `safe_tools`，写操作走 `sensitive_tools`（执行前中断等待用户确认）。子助理完成后通过 `leave_skill` 返回主助理。

5. **记忆持久化** — `MemorySaver` 保存全部对话历史；`dialog_state` 栈记录当前激活的子助理，多轮对话中断恢复时可精准路由回对应子助理。

**可调用的工具清单：**

| 类别     | 工具                                                          | 说明                                               |
| -------- | ------------------------------------------------------------- | -------------------------------------------------- |
| 航班     | `fetch_user_flight_information`                               | 查询当前乘客的机票和座位信息                       |
| 航班     | `search_flights`                                              | 按出发/到达机场、时间范围搜索航班                  |
| 航班     | `update_ticket_to_new_flight`                                 | 改签（距起飞需 ≥ 3 小时）                          |
| 航班     | `cancel_ticket`                                               | 退票（验证乘客身份后删除）                         |
| 酒店     | `search_hotels`                                               | 按地点/名称搜索酒店                                |
| 酒店     | `book_hotel` / `update_hotel` / `cancel_hotel`                | 订/改/取消酒店                                     |
| 租车     | `search_car_rentals`                                          | 按地点/名称搜索租车                                |
| 租车     | `book_car_rental` / `update_car_rental` / `cancel_car_rental` | 订/改/取消租车                                     |
| 旅行推荐 | `search_trip_recommendations`                                 | 按地点/关键词搜索景点活动                          |
| 旅行推荐 | `book_excursion` / `update_excursion` / `cancel_excursion`    | 订/改/取消行程项目                                 |
| 政策查询 | `lookup_policy`                                               | 向量检索 FAQ（余弦相似度，OpenRouter bge-m3 嵌入）  |
| 网络搜索 | `tavily_tool` (`TavilySearchResults`)                         | 实时搜索兜底，最多返回 1 条结果                     |

---

### 技术架构

| 层次           | 技术选型                            | 说明                                        |
| -------------- | ----------------------------------- | ------------------------------------------- |
| **智能体编排** | LangGraph                           | 状态机驱动的多步骤 Agent 工作流             |
| **LLM 接入**   | OpenRouter (OpenAI 兼容)            | 通过 OpenRouter 统一接入多模型              |
| **工具调用**   | LangChain Tools                     | 封装在 `tools/` 模块中                      |
| **对话管理**   | LangGraph 图对话                    | 实现在 `graph_chat/` 模块中                 |
| **向量检索**   | OpenAI Embeddings (bge-m3)          | 通过 OpenRouter 调用 bge-m3 嵌入模型        |
| **API 服务**   | FastAPI + Uvicorn                   | RESTful 接口层，含 JWT 认证与用户管理       |
| **Web UI**     | Gradio                              | 基于 Gradio 的交互式聊天界面                |
| **配置管理**   | Dynaconf                            | 多环境配置，支持 YAML + 环境变量覆盖        |
| **数据库 ORM** | SQLAlchemy 2.x                      | 用户管理数据（MySQL），工具数据用 SQLite    |
| **鉴权**       | JWT (python-jose) + bcrypt          | Token 验证中间件 + 密码哈希                 |
| **结构化数据** | SQLite + SQLAlchemy                 | 轻量级本地数据库（航班/酒店数据）           |
| **追踪调试**   | LangSmith                           | Agent 执行链路可观测性                      |

### 项目结构

```
ctrip_agent/
├── graph_chat/
│   ├── graph_gradio.py  # Gradio Web UI 入口
│   ├── workflow.py       # 命令行模式入口（图构建 + 主循环）
│   └── ...              # 助理、子图、状态等模块
├── tools/               # LangChain 工具集（航班查询、酒店查询等）
├── requirements.txt     # 项目依赖
└── travel.sqlite        # SQLite 数据库文件
```

### 快速启动

```shell
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量（复制后填入 API Key）
cp .env.example .env

# 3. 启动 FastAPI 服务（推荐）
python main.py

# 4. 或启动 Gradio Web UI
python graph_chat/graph_gradio.py
```

### 环境变量

在 `.env` 文件中配置以下字段：

```env
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_EMBEDDINGS_MODEL_NAME=baai/bge-m3
LLM_MODEL_NAME=your_llm_model_name
LANGSMITH_API_KEY=your_langsmith_api_key   # 可选，用于追踪调试
```

---

### 功能迭代

**[FastAPI 接口层] RESTful API 服务**

- **`main.py` 重写**：从占位脚本改为完整的 FastAPI 服务入口，通过 `Server` 类统一初始化日志、中间件、CORS、路由，使用 `uvicorn` 启动
- **新增 `api/` 模块**：包含工作流调用接口（`/api/graph/`）与用户管理接口（注册/登录/CRUD）
  - `api/graph_api/graph_views.py`：POST `/api/graph/`，接收用户输入与会话配置，驱动 LangGraph 工作流，处理普通提问与敏感操作确认（`y`），中断时返回确认提示
  - `api/graph_api/graph_schemas.py`：定义 `GrapConfigurableSchema`（`passenger_id` + `thread_id`）、`BaseGraphSchema`、`GraphRspSchema`
  - `api/system_mgt/user_views.py`：注册、登录、Auth 表单、查询、修改、批量删除用户
  - `api/system_mgt/user_schemas.py`：用户相关 Pydantic Schema 定义
- **新增 `config/` 模块**：基于 Dynaconf 管理多环境配置，`development.yml` 包含数据库（MySQL）、JWT 密钥、白名单、默认密码等
- **新增 `db/` 模块**：SQLAlchemy ORM 层
  - `db/__init__.py`：构建数据库引擎与 Session 工厂，定义 `DBModelBase`（含 `id`/`create_time`/`update_time` 公共字段）
  - `db/dao.py`：泛型 `BaseDAO[Model, Create, Update]`，封装增删改查通用操作
  - `db/system_mgt/models.py`：`UserModel` 定义（用户名、密码、手机、邮箱、头像等）
  - `db/system_mgt/user_dao.py`：`UserDao` 继承 `BaseDAO`，扩展按用户名查询、批量删除（先清关联角色）
- **新增 `utils/` 模块**：
  - `middlewares.py`：JWT Token 验证中间件，白名单放行，解码后将 `username` 写入 `request.state`
  - `jwt_utils.py`：使用 `python-jose` 生成/验证 JWT，过期时间从配置读取
  - `password_hash.py`：bcrypt 密码哈希与验证
  - `cors.py`：CORS 跨域配置，允许来源从 `settings.ORIGINS` 读取
  - `handler_error.py`：全局异常处理注册
  - `docs_oauth2.py`：自定义 `MyOAuth2PasswordBearer`，使 Swagger UI 支持 Bearer 认证
  - `dependencies.py`：`get_db()` FastAPI 依赖注入，管理 SQLAlchemy Session 生命周期
- **`tools/__init__.py` 新增路径常量**：将项目根目录、数据库文件路径（`db`、`local_file`、`backup_file`）统一在包级别定义，各工具模块改为从此处导入，消除重复路径拼接逻辑
- **`graph_chat/workflow.py` 清理**：注释掉命令行交互主循环（`draw_graph`、`session_id`、`while True` 输入循环），工作流图对象 `graph` 保留供 API 层直接调用

**[Gradio Web UI] 交互式聊天界面**

- 新增 `graph_chat/graph_gradio.py`，基于 Gradio 构建 Web 聊天界面，支持多轮对话与敏感操作确认
- 搜索工具从 `langchain-tavily` 专用包迁移至 `langchain-community` 内置的 `TavilySearchResults`
- 依赖精简：移除 Neo4j/知识图谱、本地嵌入模型（Sentence Transformers/torch）、智谱 AI 等重型依赖，新增 Gradio/FastAPI/Uvicorn

**[拆分多 Agent] 多助理协作架构**

- **主助理 + 四子助理架构**：主助理 `primary_assistant` 负责查询与任务分发，航班/酒店/租车/旅游各有独立子助理处理写操作，通过 Pydantic 模型（`ToFlightBookingAssistant` 等）触发委派
- **对话状态栈 `dialog_state`**：使用 `Annotated[list, update_dialog_stack]` 管理当前激活的子助理；入栈（`entry_node`）进入子助理，出栈（`leave_skill` → `"pop"`）返回主助理
- **子助理工具安全分级**：每个子助理内部将工具分为 `safe_tools`（只读查询）和 `sensitive_tools`（写操作），通过条件路由分别处理
- **敏感工具中断确认**：`interrupt_before` 仅针对四个子助理的 `*_sensitive_tools` 节点，执行前暂停等待用户输入 `y` 确认，拒绝则以 `ToolMessage` 回传原因
- **`CompleteOrEscalate` 机制**：子助理完成任务或用户改变意图时，调用此工具触发 `leave_skill`，弹出对话栈回到主助理

**[敏感工具区分] 流程节点重构**

- **工具安全分级**：拆分原 `part_1_tools`，按操作性质分为 `safe_tools`（只读查询）和 `sensitive_tools`（写操作），并提取 `sensitive_tool_names` 集合供后续权限判断
- **用户信息预加载节点**：新增 `fetch_user_info` 节点，在助手调用前主动调用 `fetch_user_flight_information` 拉取乘客航班信息写入 `State.user_info`
- **工具调用中断确认**：编译图时加入 `interrupt_before`，敏感工具调用前暂停等待用户确认，实现人在回路（Human-in-the-loop）

**[项目初始化] 基础架构搭建**

- 在 `tools/` 模块中完成航班、酒店、租车、旅行推荐、政策查询等工具函数的封装
- 基于 LangGraph 搭建 `assistant → tools → assistant` 基础循环图，支持多轮工具调用与对话管理

---

## 多 Agent 架构详解

### 整体架构

采用**主助理 + 四个专业子助理**的多 Agent 架构。主助理负责意图识别与查询，写操作委派给对应子助理独立处理。

```
                        ┌──────────────────┐
                        │     __start__     │
                        └────────┬─────────┘
                                 ▼
                        ┌──────────────────┐
                        │  fetch_user_info  │  预加载用户航班信息 → State.user_info
                        └────────┬─────────┘
                                 ▼
                          route_to_workflow（基于 dialog_state 栈路由）
                                 │
           ┌─────────────────────┼─────────────────────────────────┐
           ▼                     ▼                                 ▼
    ┌─────────────┐    ┌──────────────────┐              恢复到当前活跃的
    │ 首次进入     │    │  primary_assistant │ ◄── leave_skill  子助理（多轮场景）
    │ dialog_state │    └────────┬─────────┘
    │ 为空         │             │
    └──────┬──────┘    ┌────────┼────────────┬──────────────┬──────────────┐
           │           ▼        ▼            ▼              ▼              ▼
           │       查询/搜索  航班任务     租车任务       酒店任务       旅游任务
           │           │        │            │              │              │
           │           ▼        ▼            ▼              ▼              ▼
           │   primary_    enter_update  enter_book_   enter_book_   enter_book_
           │   assistant   _flight       car_rental    hotel         excursion
           │   _tools         │            │              │              │
           │      │           ▼            ▼              ▼              ▼
           │      │      update_flight book_car_     book_hotel    book_excursion
           │      │       ┌──┴──┐     rental          ┌──┴──┐       ┌──┴──┐
           │      │       ▼     ▼     ┌──┴──┐         ▼     ▼       ▼     ▼
           │      │     safe  sensitive safe sensitive safe sensitive safe sensitive
           │      │     tools  tools⚠️ tools tools⚠️  tools tools⚠️  tools tools⚠️
           │      │
           ▼      ▼                    ⚠️ = interrupt_before（需用户确认）
          END  ──►primary_assistant
```

### 核心组件说明

#### 1. State 状态定义 (`graph_chat/state.py`)

```python
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]   # 对话消息列表
    user_info: str                                         # 预加载的用户航班信息
    dialog_state: Annotated[list[Literal[...]], update_dialog_stack]  # 对话状态栈
```

- `messages`：使用 `add_messages` reducer 自动追加消息
- `user_info`：由 `fetch_user_info` 节点在图启动时填充
- `dialog_state`：栈结构，跟踪当前激活的子助理。入栈时 `push` 子助理名，出栈时传 `"pop"` 弹出栈顶

#### 2. 图构建流程 (`graph_chat/workflow.py` / `graph_chat/graph_gradio.py`)

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1 | `add_node("fetch_user_info")` | 预加载用户信息节点 |
| 2 | `add_edge(START, "fetch_user_info")` | 图的入口 |
| 3 | `build_flight_graph(builder)` 等 | 注册四个子工作流 |
| 4 | `add_node("primary_assistant")` | 主助理节点 |
| 5 | `add_conditional_edges("fetch_user_info", route_to_workflow)` | 基于 `dialog_state` 路由 |
| 6 | `add_conditional_edges("primary_assistant", route_primary_assistant)` | 主助理出口路由 |
| 7 | `graph = builder.compile(interrupt_before=[...])` | 编译图，配置敏感工具中断点 |

#### 3. 路由逻辑

**`route_to_workflow`** — `fetch_user_info` 之后的第一个路由：
- `dialog_state` 为空 → 进入 `primary_assistant`（首次对话）
- `dialog_state` 非空 → 返回栈顶子助理（多轮恢复场景）

**`route_primary_assistant`** — 主助理的出口路由：
- LLM 调用 `ToFlightBookingAssistant` → 进入 `enter_update_flight`
- LLM 调用 `ToBookCarRental` → 进入 `enter_book_car_rental`
- LLM 调用 `ToHotelBookingAssistant` → 进入 `enter_book_hotel`
- LLM 调用 `ToBookExcursion` → 进入 `enter_book_excursion`
- LLM 调用普通工具（搜索/政策） → 进入 `primary_assistant_tools`
- LLM 无工具调用（纯文本） → `END`

**子助理内部路由**（以航班为例）：
- 所有 tool_calls 都是 safe_tools → 走 `update_flight_safe_tools`
- 存在 sensitive tool → 走 `update_flight_sensitive_tools`（中断等待确认）
- 调用 `CompleteOrEscalate` → 走 `leave_skill` 返回主助理

#### 4. 子助理进入/退出机制

**进入**（`entry_node.py`）：
```
primary_assistant → ToFlightBookingAssistant (tool_call)
    → enter_update_flight (入口节点)
        → 写入 dialog_state: "update_flight"  # 入栈
        → 生成 ToolMessage 通知子助理接管
    → update_flight (子助理开始工作)
```

**退出**（`build_child_graph.py`）：
```
update_flight → CompleteOrEscalate (tool_call)
    → leave_skill
        → 写入 dialog_state: "pop"  # 出栈
        → 生成 ToolMessage 通知主助理恢复
    → primary_assistant (主助理接管)
```

#### 5. 敏感工具确认流程

```
用户: "帮我取消机票"
    → primary_assistant 委派给 update_flight 子助理
    → update_flight 调用 cancel_ticket (sensitive_tool)
    → 图在 update_flight_sensitive_tools 中断 ⏸️
    → 终端打印: "您是否批准上述操作？输入'y'继续"
    → 用户输入 'y': graph.stream(None, config) 继续执行
    → 用户输入其他: ToolMessage(content="拒绝原因") 回传给 LLM
```

#### 6. 项目结构

```
ctrip_agent/
├── main.py                # FastAPI 服务入口（Server 类）
├── api/
│   ├── routers.py         # 主路由注册
│   ├── schemas.py         # 基础 Schema（InDBMixin）
│   ├── graph_api/
│   │   ├── graph_views.py    # POST /api/graph/ 工作流接口
│   │   └── graph_schemas.py  # 工作流请求/响应 Schema
│   └── system_mgt/
│       ├── user_views.py     # 用户管理接口（注册/登录/CRUD）
│       └── user_schemas.py   # 用户 Schema
├── config/
│   ├── __init__.py        # Dynaconf 配置加载
│   ├── development.yml    # 开发环境配置
│   └── log_config.py      # 日志配置
├── db/
│   ├── __init__.py        # SQLAlchemy 引擎 + DBModelBase
│   ├── dao.py             # 通用 BaseDAO（泛型增删改查）
│   └── system_mgt/
│       ├── models.py      # UserModel
│       └── user_dao.py    # UserDao
├── utils/
│   ├── middlewares.py     # JWT Token 验证中间件
│   ├── jwt_utils.py       # JWT 生成与验证
│   ├── password_hash.py   # bcrypt 密码哈希
│   ├── cors.py            # CORS 跨域配置
│   ├── handler_error.py   # 全局异常处理
│   ├── docs_oauth2.py     # Swagger UI Bearer 认证
│   └── dependencies.py    # get_db 依赖注入
├── graph_chat/
│   ├── graph_gradio.py    # Gradio Web UI 入口（图构建 + 聊天界面）
│   ├── workflow.py        # 工作流图构建（graph 对象供 API 调用）
│   ├── state.py           # State 定义（messages, user_info, dialog_state）
│   ├── assistant.py       # CtripAssistant 类 + 主助理 prompt/tools
│   ├── agent_assistant.py # 四个子助理的 prompt/tools 定义
│   ├── build_child_graph.py  # 子工作流构建（节点/边/路由/leave_skill）
│   ├── entry_node.py      # 子助理入口节点工厂函数
│   ├── base_data_model.py # Pydantic 委派模型 + CompleteOrEscalate
│   ├── llm_tavily.py      # LLM 和 TavilySearchResults 初始化
│   └── draw_png.py        # 图可视化
├── tools/
│   ├── __init__.py        # 项目根路径 + 数据库路径常量
│   ├── flights_tools.py   # 航班工具（查询/改签/退票）
│   ├── hotels_tools.py    # 酒店工具（搜索/预订/修改/取消）
│   ├── car_tools.py       # 租车工具
│   ├── trip_tools.py      # 旅游推荐工具
│   ├── retriever_vector.py   # 政策向量检索（OpenRouter bge-m3 嵌入）
│   ├── tools_handler.py   # ToolNode 封装 + 兜底 + 打印
│   └── init_db.py         # 数据库初始化/日期更新
├── travel.sqlite          # 原始数据备份
├── travel_new.sqlite      # 运行时数据库（每次 update_dates 重置）
└── requirements.txt
```

# Reference

## 环境管理 pyenv + venv

pyenv 类似于 Node.js 上的 nvm，可以在本机安装和切换多个 Python 版本。venv 是 Python 内置的虚拟环境工具，用于隔离项目依赖。

---

### 一、安装 pyenv（macOS）

```shell
brew update
brew install pyenv
```

#### 配置 Shell 初始化

在 `~/.zshrc` 末尾添加以下内容（按照 pyenv 官方文档要求），否则终端仍会使用系统级 Python：

```shell
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
```

修改后重新加载配置或重开终端：

```shell
source ~/.zshrc
```

---

### 二、管理 Python 版本

```shell
# 查看当前已安装的所有版本（* 表示当前激活版本）
pyenv versions

# 查看所有可安装的版本
pyenv install --list

# 安装指定版本
pyenv install 3.11.9

# 设置全局默认版本
pyenv global 3.11.9

# 设置项目本地版本（在项目目录下执行，会生成 .python-version 文件）
pyenv local 3.11.9

# 验证当前版本
python --version
```

---

### 三、配置虚拟环境 venv

在项目目录下，使用 pyenv 管理的 Python 创建虚拟环境：

```shell
# 创建虚拟环境（目录名约定为 .venv）
python -m venv .venv

# 激活虚拟环境
source .venv/bin/activate

# 验证虚拟环境已激活（路径应指向 .venv 内部）
which python

# 退出虚拟环境
deactivate
```

> `.venv` 目录应加入 `.gitignore`，不提交到版本控制。

---

### 四、依赖管理

```shell
# 安装依赖
pip install <package>

# 导出当前环境依赖（用于团队共享）
pip freeze > requirements.txt

# 从 requirements.txt 安装依赖
pip install -r requirements.txt
```

---

### 五、VSCode 配置

通过 `Ctrl+Shift+P` 打开命令面板，选择 **Python: Select Interpreter**，选中 `.venv` 环境。

配置后，VSCode 内置终端打开时会自动激活对应的虚拟环境。

## 数据库配置

数据库部分使用轻量级数据库 SQLite。SQLite 是文件型数据库，无需启动独立服务进程，适合本地开发和嵌入式场景。

---

### 一、安装（macOS）

macOS 系统已内置 SQLite，可直接验证：

```shell
sqlite3 --version
```

如需安装更新版本，可通过 Homebrew：

```shell
brew install sqlite
```

---

### 二、SQLite CLI 常用命令

```shell
# 打开（或创建）数据库文件
sqlite3 travel.sqlite

# 以下命令在 sqlite3 交互环境中执行
.tables              # 列出所有表
.schema <table>      # 查看指定表的建表语句
.headers on          # 显示列名
.mode column         # 对齐列宽显示
.quit                # 退出
```

常用 SQL 操作示例：

```sql
-- 查看所有数据
SELECT * FROM flights;

-- 条件查询
SELECT * FROM flights WHERE departure = '上海';

-- 插入数据
INSERT INTO flights (id, departure, destination) VALUES (1, '上海', '北京');

-- 更新数据
UPDATE flights SET destination = '广州' WHERE id = 1;

-- 删除数据
DELETE FROM flights WHERE id = 1;
```

---

### 三、Python 集成

Python 标准库内置 `sqlite3` 模块，无需额外安装：

```python
import sqlite3

# 连接数据库（文件不存在时自动创建）
conn = sqlite3.connect("travel.sqlite")
cursor = conn.cursor()

# 查询
cursor.execute("SELECT * FROM flights")
rows = cursor.fetchall()

# 写操作后需提交
conn.commit()

# 关闭连接
conn.close()
```

推荐使用上下文管理器，自动处理连接关闭：

```python
with sqlite3.connect("travel.sqlite") as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM flights")
    rows = cursor.fetchall()
```

---

### 四、GUI 工具（可选）

推荐使用 [DB Browser for SQLite](https://sqlitebrowser.org/) 可视化查看和编辑数据库文件：

```shell
brew install --cask db-browser-for-sqlite
```
