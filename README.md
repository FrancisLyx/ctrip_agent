# 携程智能体项目

## 项目简介

基于 LangGraph 构建的旅行领域 AI 智能体，模拟携程场景，支持多轮对话与工具调用，能够完成机票/酒店查询、行程规划等任务。

### 工作流程

整体采用 LangGraph 的 `assistant → tools → assistant` 循环结构，直到 LLM 输出纯文本回复为止。

```
用户输入
   │
   ▼
┌──────────┐     有工具调用     ┌───────────────┐
│ assistant │ ──────────────► │     tools      │
│  (LLM)   │                  │ (工具节点+兜底) │
└──────────┘ ◄─────────────── └───────────────┘
   │           工具结果返回
   │ 纯文本回复
   ▼
输出给用户（循环等待下一轮）
```

**各环节说明：**

1. **入口** (`workflow.py`) — 每轮读取用户输入，以 `stream_mode="values"` 流式执行图，并打印每步事件。会话通过 `thread_id` 隔离，`passenger_id` 随配置注入。

2. **assistant 节点** (`graph_chat/assistant.py`) — 核心是 `CtripAssistant` 类：
   - 从 `config` 中取出 `passenger_id` 追加到 State，让 LLM 感知当前用户身份
   - 调用 `GPT-4o`（带系统提示：角色描述 + 当前时间 + 用户信息）
   - 如果 LLM 返回空内容，自动追加 `"请提供一个真实的输出"` 重试，直到获得有效回复

3. **tools 节点** (`tools/tools_handler.py`) — 用 `ToolNode` 执行 LLM 选择的工具，调用失败时通过 `with_fallbacks` 兜底，将错误封装成 `ToolMessage` 回传给 LLM 自动纠错。

4. **条件路由** — `tools_condition` 判断 LLM 最新消息是否含 `tool_calls`：有则转 tools 节点，无则结束本轮。

5. **记忆持久化** — `MemorySaver` 在内存中保存全部对话历史，下一轮输入时历史消息自动带入上下文。

**可调用的工具清单：**

| 类别 | 工具 | 说明 |
|------|------|------|
| 航班 | `fetch_user_flight_information` | 查询当前乘客的机票和座位信息 |
| 航班 | `search_flights` | 按出发/到达机场、时间范围搜索航班 |
| 航班 | `update_ticket_to_new_flight` | 改签（距起飞需 ≥ 3 小时） |
| 航班 | `cancel_ticket` | 退票（验证乘客身份后删除） |
| 酒店 | `search_hotels` | 按地点/名称搜索酒店 |
| 酒店 | `book_hotel` / `update_hotel` / `cancel_hotel` | 订/改/取消酒店 |
| 租车 | `search_car_rentals` | 按地点/名称搜索租车 |
| 租车 | `book_car_rental` / `update_car_rental` / `cancel_car_rental` | 订/改/取消租车 |
| 旅行推荐 | `search_trip_recommendations` | 按地点/关键词搜索景点活动 |
| 旅行推荐 | `book_excursion` / `update_excursion` / `cancel_excursion` | 订/改/取消行程项目 |
| 政策查询 | `lookup_policy` | 向量检索 FAQ（余弦相似度，OpenRouter bge-m3 嵌入） |
| 网络搜索 | `tavily_tool` | 实时搜索兜底，最多返回 1 条结果 |

---

### 技术架构

| 层次 | 技术选型 | 说明 |
|------|----------|------|
| **智能体编排** | LangGraph | 状态机驱动的多步骤 Agent 工作流 |
| **LLM 接入** | OpenAI API / 智谱 AI (ZhipuAI) | 双模型支持，兼容国内外场景 |
| **工具调用** | LangChain Tools | 封装在 `tools/` 模块中 |
| **对话管理** | LangGraph 图对话 | 实现在 `graph_chat/` 模块中 |
| **向量检索** | Sentence Transformers + HuggingFace | 本地嵌入模型，用于语义搜索 |
| **知识图谱** | Neo4j + neo4j-graphrag | 旅行知识图谱存储与查询 |
| **结构化数据** | SQLite + SQLAlchemy | 轻量级本地数据库（航班/酒店数据） |
| **追踪调试** | LangSmith | Agent 执行链路可观测性 |

### 项目结构

```
ctrip_agent/
├── main.py              # 入口文件
├── tools/               # LangChain 工具集（航班查询、酒店查询等）
├── graph_chat/          # LangGraph 对话图定义
├── requirements.txt     # 项目依赖
└── travel.sqlite        # SQLite 数据库文件
```

### 快速启动

```shell
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量（复制后填入 API Key）
cp .env.example .env

# 3. 运行
python main.py
```

### 环境变量

在 `.env` 文件中配置以下字段：

```env
OPENAI_API_KEY=your_openai_api_key
ZHIPUAI_API_KEY=your_zhipuai_api_key
LANGSMITH_API_KEY=your_langsmith_api_key   # 可选，用于追踪调试
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

---

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
