# 使用AI大模型

import os

from langchain_community.tools import TavilySearchResults
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(
    temperature=0,
    model=os.getenv("LLM_MODEL_NAME"),
    openai_api_key=os.getenv("OPENROUTER_API_KEY"),
    openai_api_base=os.getenv("OPENROUTER_BASE_URL"),
)


# llm = ChatOpenAI(  # 用的自己的服务器部署的大模型
#     temperature=0.8,
#     model="Qwen-7B",
#     openai_api_key="EMPTY",
#     openai_api_base="http://localhost:6006/v1",
# )

# llm = ChatOpenAI(  # openai的
#     temperature=0,
#     model='gpt-4o',
#     api_key="sk-doD81WgxSoF9A6xYzhgW7GUh5frRwPETI8mDq3ce4UaWnCPF",
#     base_url="https://xiaoai.plus/v1")

# llm = ChatOpenAI(  # openai的
#     temperature=0,
#     model='claude-3-7-sonnet-20250219',
#     api_key="sk-doD81WgxSoF9A6xYzhgW7GUh5frRwPETI8mDq3ce4UaWnCPF",
#     base_url="https://xiaoai.plus/v1")

# llm = ChatOpenAI(
#     temperature=0,
#     model='deepseek-chat',
#     api_key="sk-6c90758171ea4cf799171ec689a26444",
#     base_url="https://api.deepseek.com")


# 初始化搜索工具，限制结果数量为2
os.environ["TAVILY_API_KEY"] = "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"
tavily_tool = TavilySearchResults(max_results=1)
