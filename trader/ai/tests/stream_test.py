from openai import OpenAI
from ai.config import *
from datetime import datetime

client = OpenAI(
    api_key=token,
    base_url=kimi_url,
)

system_prompt = f"""
你是 Kimi，今天的日期是 {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}。使用中文回复。
"""

response = client.chat.completions.create(
    model="kimi-k2.5",
    messages=[
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user", "content": "你好，我叫李雷，1+1等于多少？"
        }
    ],
    stream=True
)

'''
流式 官方举例
collected_messages = []
for idx, chunk in enumerate(response):
    # print("Chunk received, value: ", chunk)
    chunk_message = chunk.choices[0].delta
    if not chunk_message.content:
        continue
    collected_messages.append(chunk_message)  # save the message
    print(f"#{idx}: {''.join([m.content for m in collected_messages])}")
print(f"Full conversation received: {''.join([m.content for m in collected_messages])}")
'''

collected_messages = []
for idx, chunk in enumerate(response):
    #print("Chunk received, value: ", chunk)       #调试用 正式使用时应注释此行
    chunk_message = chunk.choices[0].delta
    if not chunk_message.content:
        continue
    collected_messages.append(chunk_message)  # save the message
    if chunk_message.content:
        print(chunk_message.content, end="", flush=True)
#print("")
#print(f"Full conversation received: {''.join([m.content for m in collected_messages])}")
