import json
import re
from openai import OpenAI
from core.config import load_config


def parse_json_response(raw_response):
    try:
        return json.loads(raw_response.strip())
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw_response)
        if match:
            return json.loads(match.group())
        raise


def call_llm(system_prompt, user_prompt, json_mode=False, temperature=0.7):
    config = load_config()
    if not config["api_key"] or config["api_key"] == "your-api-key-here":
        raise RuntimeError(
            "API Key 未配置。请编辑 .env 文件，设置 OPENAI_API_KEY 后再试。"
        )

    client = OpenAI(
        api_key=config["api_key"],
        base_url=config["base_url"],
        timeout=120.0,
        max_retries=1,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    kwargs = {
        "model": config["model"],
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def call_llm_stream(system_prompt, user_prompt, temperature=0.7):
    """流式 LLM 调用，yield token chunks。"""
    config = load_config()
    if not config["api_key"] or config["api_key"] == "your-api-key-here":
        raise RuntimeError(
            "API Key 未配置。请编辑 .env 文件，设置 OPENAI_API_KEY 后再试。"
        )

    client = OpenAI(
        api_key=config["api_key"],
        base_url=config["base_url"],
        timeout=120.0,
        max_retries=1,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    stream = client.chat.completions.create(
        model=config["model"],
        messages=messages,
        temperature=temperature,
        stream=True,
    )
    for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
