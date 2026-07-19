"""
MiniMax LLM 服务
使用 MiniMax API 进行文本生成
"""
import requests
import json
from typing import List, Dict, Any, Optional
from app.config import Config


class MiniMaxLLM:
    """MiniMax 大语言模型服务"""

    BASE_URL = "https://api.minimax.chat/v1"

    def __init__(self, api_key: str = None, model: str = None):
        """
        初始化 MiniMax LLM

        Args:
            api_key: MiniMax API Key
            model: 模型名称，默认使用 MiniMax-Text-01
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

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }

        print(f"[MiniMax API] 调用模型: {self.model}")
        print(f"[MiniMax API] 请求URL: {url}")
        print(f"[MiniMax API] 消息数量: {len(messages)}")

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            print(f"[MiniMax API] 响应状态码: {response.status_code}")

            # 如果不是200，打印响应内容用于调试
            if response.status_code != 200:
                print(f"[MiniMax API] 错误响应: {response.text[:500]}")

            response.raise_for_status()
            result = response.json()

            # 调试：打印原始响应
            import sys
            print(f"[MiniMax API] 原始响应: {result}", flush=True)
            sys.stdout.flush()

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
                    "usage": result.get("usage", {}),
                    "raw": result
                }
            elif "output" in result:
                # MiniMax 特有格式：直接在 output 中
                return {
                    "status_code": 200,
                    "output": result["output"],
                    "usage": result.get("usage", {}),
                    "raw": result
                }
            elif "text" in result:
                # 文本生成格式
                return {
                    "status_code": 200,
                    "output": {
                        "text": result["text"]
                    },
                    "usage": result.get("usage", {}),
                    "raw": result
                }
            else:
                return {
                    "status_code": 500,
                    "message": "API返回格式异常，未知响应结构",
                    "raw": result
                }

        except requests.exceptions.Timeout:
            print("[MiniMax API] 请求超时")
            return {
                "status_code": 408,
                "message": "请求超时"
            }
        except requests.exceptions.RequestException as e:
            print(f"[MiniMax API] 请求失败: {str(e)}")
            return {
                "status_code": 500,
                "message": f"请求失败: {str(e)}"
            }
        except json.JSONDecodeError as e:
            print(f"[MiniMax API] JSON解析失败: {e}")
            return {
                "status_code": 500,
                "message": "响应JSON解析失败"
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