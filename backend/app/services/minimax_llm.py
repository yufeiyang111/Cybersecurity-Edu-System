"""
MiniMax LLM 服务
使用 MiniMax API 进行文本生成
"""
import json
import logging
from typing import Any, Dict, List

import requests

from app.config import Config


logger = logging.getLogger(__name__)


class MiniMaxLLM:
    """MiniMax 大语言模型服务"""

    BASE_URL = "https://api.minimaxi.com/v1"

    def __init__(self, api_key: str = None, model: str = None):
        """
        初始化 MiniMax LLM

        Args:
            api_key: MiniMax API Key
            model: 模型名称，默认使用 MiniMax-M2.7
        """
        self.api_key = api_key or Config.MINIMAX_API_KEY
        self.model = model or Config.MINIMAX_MODEL
        self.api_base = Config.MINIMAX_API_BASE

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> Dict[str, Any]:
        """
        发送对话请求

        Args:
            messages: 消息列表 [{"role": "user/assistant/system", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大生成token数

        Returns:
            API 响应结果
        """
        url = f"{self.api_base}/text/chatcompletion_v2"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        timeout_seconds = kwargs.pop("timeout_seconds", 120)
        try:
            timeout_seconds = max(0.1, float(timeout_seconds))
        except (TypeError, ValueError):
            timeout_seconds = 120

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }

        # Only safe diagnostic metadata is logged. Request bodies, auth headers, and endpoint URLs are excluded.
        logger.info("MiniMax API request started (message_count=%d)", len(messages))

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
            if response.status_code != 200:
                # Provider error bodies can echo prompts or sensitive context, so never log them.
                logger.warning(
                    "MiniMax API returned non-success status (status_code=%d)",
                    response.status_code,
                )
            else:
                logger.info(
                    "MiniMax API response received (status_code=%d)",
                    response.status_code,
                )

            response.raise_for_status()
            result = response.json()

            # MiniMax /text/chatcompletion_v2 端点可能返回不同格式
            # 尝试多种可能的响应格式
            choices = result.get("choices")
            if choices is not None and len(choices) > 0:
                # 标准 chat completion 格式
                return {
                    "status_code": 200,
                    "output": {
                        "choices": result["choices"]
                    },
                    "usage": result.get("usage", {})
                }
            elif "output" in result:
                # MiniMax 特有格式：直接在 output 中
                return {
                    "status_code": 200,
                    "output": result["output"],
                    "usage": result.get("usage", {})
                }
            elif "text" in result:
                # 文本生成格式
                return {
                    "status_code": 200,
                    "output": {
                        "text": result["text"]
                    },
                    "usage": result.get("usage", {})
                }
            else:
                logger.warning("MiniMax API returned an unsupported response structure")
                return {
                    "status_code": 500,
                    "message": "API返回格式异常，未知响应结构"
                }

        except requests.exceptions.Timeout:
            logger.warning("MiniMax API request timed out")
            return {
                "status_code": 408,
                "message": "请求超时"
            }
        except json.JSONDecodeError:
            # JSON parsing errors can embed the original provider body.
            logger.warning("MiniMax API returned invalid JSON")
            return {
                "status_code": 500,
                "message": "响应JSON解析失败"
            }
        except requests.exceptions.RequestException as exc:
            # Do not attach exception details; they can contain URLs, error bodies, or request context.
            logger.warning(
                "MiniMax API request failed (error_type=%s)",
                type(exc).__name__,
            )
            return {
                "status_code": 500,
                "message": "请求失败"
            }

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> Any:
        """
        流式对话（SSE 格式增量输出）

        Args:
            messages: 消息列表 [{"role": "user/assistant/system", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大生成token数

        Yields:
            事件字典: {"status_code": int, "delta": str, "reasoning_delta": str, "finish": bool}
        """
        url = f"{self.api_base}/text/chatcompletion_v2"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        timeout_seconds = kwargs.pop("timeout_seconds", 120)
        try:
            timeout_seconds = max(0.1, float(timeout_seconds))
        except (TypeError, ValueError):
            timeout_seconds = 120

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "use_standard_sse": True,
            **kwargs
        }

        logger.info("MiniMax streaming request started (message_count=%d)", len(messages))

        try:
            with requests.post(url, headers=headers, json=payload, timeout=timeout_seconds, stream=True) as response:
                if response.status_code != 200:
                    logger.warning(
                        "MiniMax streaming API returned non-success status (status_code=%d)",
                        response.status_code,
                    )
                    yield {
                        "status_code": response.status_code,
                        "delta": "",
                        "reasoning_delta": "",
                        "finish": True,
                    }
                    return

                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if not data or data == "[DONE]":
                        continue

                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    choices = event.get("choices")
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content") or ""
                    reasoning = delta.get("reasoning_content") or ""
                    finish = bool(choices[0].get("finish_reason"))
                    yield {
                        "status_code": 200,
                        "delta": content,
                        "reasoning_delta": reasoning,
                        "finish": finish,
                    }
                    if finish:
                        return
        except requests.exceptions.Timeout:
            logger.warning("MiniMax streaming request timed out")
            yield {
                "status_code": 408,
                "delta": "",
                "reasoning_delta": "",
                "finish": True,
            }
        except requests.exceptions.RequestException as exc:
            logger.warning(
                "MiniMax streaming request failed (error_type=%s)",
                type(exc).__name__,
            )
            yield {
                "status_code": 500,
                "delta": "",
                "reasoning_delta": "",
                "finish": True,
            }

    def generate(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> str:
        """
        简单文本生成

        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            temperature: 温度
            max_tokens: 最大token数

        Returns:
            生成的文本
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        result = self.chat(messages, temperature, max_tokens)

        if result.get("status_code") == 200:
            try:
                return result["output"]["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                return "生成内容解析失败"
        else:
            error_msg = result.get("message", "未知错误")
            return f"生成失败: {error_msg}"

    def chat_with_history(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> str:
        """
        带历史的对话

        Args:
            messages: 对话历史
            system_prompt: 系统提示
            temperature: 温度
            max_tokens: 最大token数

        Returns:
            生成的文本
        """
        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        result = self.chat(all_messages, temperature, max_tokens)

        if result.get("status_code") == 200:
            try:
                return result["output"]["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                return "生成内容解析失败"
        else:
            error_msg = result.get("message", "未知错误")
            return f"生成失败: {error_msg}"


# 全局单例
_minimax_llm = None


def get_minimax_llm() -> MiniMaxLLM:
    """获取 MiniMax LLM 单例"""
    global _minimax_llm
    if _minimax_llm is None:
        _minimax_llm = MiniMaxLLM()
    return _minimax_llm


def generate_with_minimax(
    prompt: str,
    system_prompt: str = None,
    **kwargs
) -> str:
    """便捷的生成函数"""
    llm = get_minimax_llm()
    return llm.generate(prompt, system_prompt, **kwargs)


def chat_with_minimax(
    messages: List[Dict[str, str]],
    system_prompt: str = None,
    **kwargs
) -> str:
    """便捷的对话函数"""
    llm = get_minimax_llm()
    return llm.chat_with_history(messages, system_prompt, **kwargs)
