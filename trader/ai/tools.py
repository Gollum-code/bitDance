'''
包含tools定义，使用函数func接口，tool_map映射      （func_impl实现放到其他文件里面去）
import时应全部引用

未完成 内部为部分示例代码
'''

tools = [
    {
        "type": "function",  # （固定字段）约定的字段 type，目前支持 function 作为值
        "function": {  # 当 type 为 function 时，使用 function 字段定义具体的函数内容
            "name": "search",  # 函数的名称，ai识别用，与实际函数通过tool_map对应
            "description": """ 
				通过搜索引擎搜索互联网上的内容。

				当你的知识无法回答用户提出的问题，或用户请求你进行联网搜索时，调用此工具。请从与用户的对话中提取用户想要搜索的内容作为 query 参数的值。
				搜索结果包含网站的标题、网站的地址（URL）以及网站简介。
			""",  # 函数的介绍，Kimi 大模型读取描述以正确地选择使用哪些函数
            "parameters": {  # （固定）使用 parameters 字段来定义函数接收的参数
                "type": "object",  # （固定，统一接口对参数的拆解）使用 type: object 来使 Kimi 大模型生成一个 JSON Object 参数
                "required": ["query"],  # 使用 required 字段告诉 Kimi 大模型哪些参数是必填项
                "properties": {  # properties 中是具体的参数定义，你可以定义多个参数
                    "query": {  # 在这里，key 是参数名称，value 是参数的具体定义
                        "type": "string",  # 使用 type 定义参数类型
                        "description": """
							用户搜索的内容，请从用户的提问或聊天上下文中提取。
						"""  # 使用 description 描述参数以便 Kimi 大模型更好地生成参数
                    }
                }
            }
        }
    },
    {
        "type": "function",  # 约定的字段 type，目前支持 function 作为值
        "function": {  # 当 type 为 function 时，使用 function 字段定义具体的函数内容
            "name": "crawl",  # 函数的名称，请使用英文大小写字母、数据加上减号和下划线作为函数名称
            "description": """
				根据网站地址（URL）获取网页内容。
			""",  # 函数的介绍，在这里写上函数的具体作用以及使用场景，以便 Kimi 大模型能正确地选择使用哪些函数
            "parameters": {  # 使用 parameters 字段来定义函数接收的参数
                "type": "object",  # 固定使用 type: object 来使 Kimi 大模型生成一个 JSON Object 参数
                "required": ["url"],  # 使用 required 字段告诉 Kimi 大模型哪些参数是必填项
                "properties": {  # properties 中是具体的参数定义，你可以定义多个参数
                    "url": {  # 在这里，key 是参数名称，value 是参数的具体定义
                        "type": "string",  # 使用 type 定义参数类型
                        "description": """
							需要获取内容的网站地址（URL），通常情况下从搜索结果中可以获取网站的地址。
						"""  # 使用 description 描述参数以便 Kimi 大模型更好地生成参数
                    }
                }
            }
        }
    }
]


def search_impl(query: str) -> List[Dict[str, Any]]:
    """
    search_impl 使用搜索引擎对 query 进行搜索，目前主流的搜索引擎（例如 Bing）都提供了 API 调用方式，你可以自行选择
    你喜欢的搜索引擎 API 进行调用，并将返回结果中的网站标题、网站链接、网站简介信息放置在一个 dict 中返回。

    这里只是一个简单的示例，你可能需要编写一些鉴权、校验、解析的代码。
    """
    r = httpx.get("https://your.search.api", params={"query": query})
    return r.json()


def search(arguments: Dict[str, Any]) -> Any:
    query = arguments["query"]
    result = search_impl(query)
    return {"result": result}


def crawl_impl(url: str) -> str:
    """
    crawl_url 根据 url 获取网页上的内容。

    这里只是一个简单的示例，在实际的网页抓取过程中，你可能需要编写更多的代码来适配复杂的情况，例如异步加载的数据等；同时，在获取
    网页内容后，你可以根据自己的需要对网页内容进行清洗，只保留文本或移除不必要的内容（例如广告信息等）。
    """
    #r = httpx.get(url)
    #return r.text
    return "这是一段测试桩代码，测试tool_call是否正常生效，Context Caching就是Context Caching"


def crawl(arguments: dict) -> str:
    url = arguments["url"]
    content = crawl_impl(url)
    return {"content": content}


# 通过 tool_map 将每个工具名称及其对应的函数进行映射，以便在 Kimi 大模型返回 tool_calls 时能快速找到应该执行的函数
tool_map = {
    "search": search,
    "crawl": crawl,
}