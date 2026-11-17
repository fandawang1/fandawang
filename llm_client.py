"""
大模型客户端模块 - 封装大模型 API 调用

本模块使用 OpenAI SDK 调用大模型接口，
支持流式响应和多种生成参数配置，
提供统一的客户端接口供上层业务调用。
"""

from openai import OpenAI
from config import Config


class LLMClient:
    """
    大模型客户端类 - 封装 API 调用逻辑
    
    属性:
        api_key: API 密钥
        base_url: API 基础地址
        client: OpenAI 客户端实例
    """
    
    def __init__(self, api_key=None, base_url=None):
        """
        初始化客户端
        
        参数:
            api_key: API 密钥，默认为配置中的 API_KEY
            base_url: API 基础地址，默认为配置中的 BASE_URL
        
        异常:
            ValueError: 当无法获取有效的模型配置时抛出
        """
        self.api_key = api_key or Config.API_KEY
        
        # 获取模型配置信息，确保不为 None
        model_info = Config.get_model_info()
        if not model_info:
            raise ValueError("无法获取有效的模型配置，请检查 .env 文件")
        
        self.base_url = base_url or model_info["base_url"]
        # 创建 OpenAI 客户端实例
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat(
        self,
        messages,
        model,
        temperature=0.7,
        top_p=0.9,
        max_tokens=2048,
        stream=True
    ):
        """
        调用大模型进行对话
        
        参数:
            messages: 消息列表，格式为 [{"role": "user/assistant/system", "content": "..."}]
            model: 模型名称
            temperature: 采样温度（0.0-2.0），值越高输出越随机
            top_p: 核采样参数（0.0-1.0），控制采样范围
            max_tokens: 最大生成 token 数
            stream: 是否流式响应，默认为 True
        
        返回:
            generator: 流式响应时返回生成器，逐个返回内容片段
            str: 非流式响应时返回完整响应内容
        
        异常处理:
            捕获所有异常，通过生成器返回错误信息
        """
        try:
            # 调用 OpenAI API
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                stream=stream
            )

            # 流式响应处理
            if stream:
                for chunk in response:
                    # 提取内容片段，跳过空内容
                    if chunk.choices[0].delta.content is not None:
                        yield chunk.choices[0].delta.content
            else:
                # 非流式响应，直接返回完整内容
                return response.choices[0].message.content

        except Exception as e:
            # 捕获异常并返回错误信息
            error_message = f"调用大模型 API 时出错: {str(e)}"
            yield error_message

    def create_client_for_provider(self, provider):
        """
        根据模型提供商创建专用客户端
        
        参数:
            provider: 模型提供商名称（deepseek/qwen）
        
        返回:
            LLMClient: 对应提供商的客户端实例
        """
        model_info = Config.get_model_info(provider)
        if model_info:
            return LLMClient(api_key=self.api_key, base_url=model_info["base_url"])
        # 如果提供商无效，返回当前客户端
        return self

    # def get_model_name(self, provider):
    #     """
    #     获取指定提供商的模型名称
        
    #     参数:
    #         provider: 模型提供商名称（deepseek/qwen）
        
    #     返回:
    #         str: 模型名称，如果提供商无效返回空字符串
    #     """
    #     model_info = Config.get_model_info(provider)
    #     return model_info["model_name"] if model_info else ""
