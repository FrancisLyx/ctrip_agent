import os
from datetime import datetime

from langchain_tavily import TavilySearch
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv


from graph_chat.state import State
from tools.car_tools import (
    search_car_rentals,
    book_car_rental,
    update_car_rental,
    cancel_car_rental,
)
from tools.flights_tools import (
    fetch_user_flight_information,
    search_flights,
    update_ticket_to_new_flight,
    cancel_ticket,
)
from tools.hotels_tools import search_hotels, book_hotel, update_hotel, cancel_hotel
from tools.retriever_vector import lookup_policy
from tools.trip_tools import (
    search_trip_recommendations,
    book_excursion,
    update_excursion,
    cancel_excursion,
)

load_dotenv()


def _normalize_content(content) -> str:
    """将列表格式的消息内容拍平为字符串（DeepSeek 等 API 不支持列表格式）。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text", str(item)))
        return "\n".join(parts)
    return str(content)


class CtripAssistant:

    # 自定义一个类，表示流程图的一个节点（复杂的）

    def __init__(self, runnable: Runnable):
        """
        初始化助手的实例。
        :param runnable: 可以运行对象，通常是一个Runnable类型的
        """
        self.runnable = runnable

    def __call__(self, state: State, config: RunnableConfig):
        """
        调用节点，执行助手任务
        :param state: 当前工作流的状态
        :param config: 配置: 里面有旅客的信息
        :return:
        """
        while True:
            # 创建了一个无限循环，它将一直执行直到：从 self.runnable 获取的结果是有效的。
            # 如果结果无效（例如，没有工具调用且内容为空或内容不符合预期格式），循环将继续执行，
            configuration = config.get("configurable", {})
            user_id = configuration.get("passenger_id", None)
            state = {
                **state,
                "user_info": user_id,
            }  # 从配置中得到旅客的ID，也追加到state

            # DeepSeek 等不兼容 OpenAI 多模态格式的 API 要求 content 必须为字符串
            # 将消息列表中所有 list 格式的 content 统一转为字符串
            normalized = []
            for msg in state.get("messages", []):
                if isinstance(msg.content, list):
                    msg = msg.model_copy(update={"content": _normalize_content(msg.content)})
                normalized.append(msg)
            state = {**state, "messages": normalized}

            result = self.runnable.invoke(state)
            # 如果，runnable执行完后，没有得到一个实际的输出
            if (
                not result.tool_calls
                and (  # 如果结果中没有工具调用，并且内容为空或内容列表的第一个元素没有"text"，则需要重新提示用户输入。
                    not result.content
                    or isinstance(result.content, list)
                    and not result.content[0].get("text")
                )
            ):
                messages = state["messages"] + [
                    ("user", "请提供一个真实的输出作为回应。")
                ]
                state = {**state, "messages": messages}
            else:  # 如果： runnable执行后已经得到，想要的输出，则退出循环
                break
        return {"messages": result}


# 初始化搜索工具，限制结果数量为2
os.environ["TAVILY_API_KEY"] = "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"
tavily_tool = TavilySearch(max_results=1)
# 定义工具列表，这些工具将在与用户交互过程中被调用
part_1_tools = [
    tavily_tool,
    fetch_user_flight_information,
    search_flights,
    lookup_policy,
    update_ticket_to_new_flight,
    cancel_ticket,
    search_car_rentals,
    book_car_rental,
    update_car_rental,
    cancel_car_rental,
    search_hotels,
    book_hotel,
    update_hotel,
    cancel_hotel,
    search_trip_recommendations,
    book_excursion,
    update_excursion,
    cancel_excursion,
]


def create_assistant_node() -> CtripAssistant:
    """
    创建一个助手节点
    :return: 返回一个助手节点对象
    """
    llm = ChatOpenAI(  # openai的
        temperature=0,
        model=os.getenv("DEEPSEEK_MODEL_NAME"),
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL"),
    )

    # 创建主要助理使用的提示模板
    primary_assistant_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "您是携程瑞士航空公司的客户服务助理。优先使用提供的工具搜索航班、公司政策和其他信息来帮助用户的查询。"
                "搜索时，请坚持不懈。如果第一次搜索没有结果，扩大您的查询范围。"
                "如果搜索为空，在放弃之前扩展您的搜索。\n\n当前用户:\n<User>\n{user_info}\n</User>"
                "\n当前时间: {time}.",
            ),
            ("placeholder", "{messages}"),
        ]
    ).partial(time=datetime.now())

    runnable = primary_assistant_prompt | llm.bind_tools(part_1_tools)
    return CtripAssistant(runnable)  # 创建一个类的实例
