"""
配置模块 - 负责加载和管理大模型相关配置

本模块使用 python-dotenv 从 .env 文件加载配置，
支持多模型提供商（DeepSeek、Qwen）的自动映射，
并提供配置验证功能。
"""

import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# 模型映射配置：定义不同模型提供商的默认参数
# 所有模型均使用硅基流动（SiliconFlow）接口
MODEL_MAPPING = {
    "deepseek": {
        "base_url": "https://api.siliconflow.cn/v1",
        "model_name": "deepseek-ai/DeepSeek-V3"
    },
    "qwen": {
        "base_url": "https://api.siliconflow.cn/v1",
        "model_name": "Qwen/Qwen2.5-72B-Instruct"
    }
}


class Config:
    """
    配置类 - 封装所有大模型相关配置
    
    属性:
        API_KEY: 大模型 API 密钥
        BASE_URL: API 基础地址（可选，默认使用模型映射中的地址）
        PROVIDER: 默认模型提供商（deepseek 或 qwen）
        MODEL: 模型名称（可选，默认使用模型映射中的名称）
        TEMPERATURE: 采样温度（0.0-2.0）
        TOP_P: 核采样参数（0.0-1.0）
        MAX_TOKENS: 最大生成 token 数
    """
    
    # 从环境变量读取配置，提供默认值
    API_KEY = os.getenv("LLM_API_KEY", "")
    BASE_URL = os.getenv("LLM_BASE_URL", "")
    PROVIDER = os.getenv("LLM_PROVIDER", "deepseek").lower()
    MODEL = os.getenv("LLM_MODEL", "")
    
    TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    TOP_P = float(os.getenv("LLM_TOP_P", "0.3"))
    MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))

    @classmethod
    def get_model_info(cls, provider=None):
        """
        获取指定模型提供商的配置信息

        参数:
            cls: 类对象本身，用于访问类属性（如 PROVIDER、BASE_URL、MODEL）
            provider: 模型提供商名称（deepseek 或 qwen），默认为配置的 PROVIDER

        返回:
            dict: 包含 base_url 和 model_name 的字典，若提供商无效返回 None
        """
        if not provider:
            provider = cls.PROVIDER
            # 未显式指定 provider 时，允许环境变量覆盖映射默认值
            mapping = MODEL_MAPPING.get(provider)
            if mapping:
                return {
                    "base_url": cls.BASE_URL if cls.BASE_URL else mapping["base_url"],
                    "model_name": cls.MODEL if cls.MODEL else mapping["model_name"]
                }
            return None

        # 显式指定了 provider，直接使用映射中的默认值，前端选择优先
        if provider in MODEL_MAPPING:
            mapping = MODEL_MAPPING[provider]
            return {
                "base_url": mapping["base_url"],
                "model_name": mapping["model_name"]
            }
        return None

    @classmethod
    def validate(cls):
        """
        验证配置的有效性
        
        返回:
            list: 错误信息列表，验证通过返回空列表
        """
        errors = []
        
        # 检查必填项
        if not cls.API_KEY:
            errors.append("LLM_API_KEY 是必需的配置项")
        
        # 检查提供商有效性
        if cls.PROVIDER not in MODEL_MAPPING:
            errors.append(f"LLM_PROVIDER 必须是 deepseek 或 qwen，当前值: {cls.PROVIDER}")
        
        # 检查参数范围
        if cls.TEMPERATURE < 0.0 or cls.TEMPERATURE > 2.0:
            errors.append(f"LLM_TEMPERATURE 必须在 0.0-2.0 之间，当前值: {cls.TEMPERATURE}")
        
        if cls.TOP_P < 0.0 or cls.TOP_P > 1.0:
            errors.append(f"LLM_TOP_P 必须在 0.0-1.0 之间，当前值: {cls.TOP_P}")
        
        if cls.MAX_TOKENS < 1 or cls.MAX_TOKENS > 8192:
            errors.append(f"LLM_MAX_TOKENS 必须在 1-8192 之间，当前值: {cls.MAX_TOKENS}")
        
        return errors

    @classmethod
    def get_default_params(cls):
        """
        获取默认的生成参数
        
        返回:
            dict: 包含 temperature、top_p、max_tokens 的字典
        """
        return {
            "temperature": cls.TEMPERATURE,
            "top_p": cls.TOP_P,
            "max_tokens": cls.MAX_TOKENS,
        }

    @classmethod
    def get_available_models(cls):
        """
        获取所有可用的模型提供商列表
        
        返回:
            list: 模型提供商名称列表
        """
        return list(MODEL_MAPPING.keys())
