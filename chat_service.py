"""
业务逻辑层 - 对话服务核心模块

本模块封装了对话助手的核心业务逻辑，包括：
- 会话管理（新建、删除、查询）
- 消息发送与处理
- 提示词模板系统
- 角色化助手功能
- 上下文压缩（长对话处理）
- 结构化输出控制
- 幻觉检测机制

是连接数据库层和 UI 层的核心桥梁。
"""

from database import (
    create_conversation,
    delete_conversation,
    list_conversations,
    get_messages,
    add_message,
    update_conversation_title,
    update_conversation_model,
    get_conversation_by_id
)
from llm_client import LLMClient
from config import Config

# ==================== 角色模板配置 ====================

# 角色模板字典，定义不同角色的系统提示词
# 每个角色包含名称、描述和系统提示词
ROLE_TEMPLATES = {
    "default": {
        "name": "默认助手",
        "description": "一个友好的通用对话助手",
        "system_prompt": "你是一个友好的智能助手，善于回答各种问题。请用简洁明了的语言回答用户的问题。"
    },
    "tech": {
        "name": "技术专家",
        "description": "精通编程和技术问题",
        "system_prompt": "你是一位资深软件工程师，精通Python、JavaScript、Java等多种编程语言，以及系统架构设计。请用专业但易懂的语言回答技术问题，并提供代码示例。"
    },
    "teacher": {
        "name": "辅导老师",
        "description": "耐心的知识传授者",
        "system_prompt": "你是一位耐心的老师，擅长用通俗易懂的方式讲解知识。请详细解释概念，并提供示例帮助理解。"
    },
    "writer": {
        "name": "文案作家",
        "description": "擅长写作和文案创作",
        "system_prompt": "你是一位专业作家，擅长撰写各类文案。请提供优美、流畅的文字，符合用户的写作需求。"
    },
    "analyst": {
        "name": "数据分析专家",
        "description": "擅长数据分析和解读",
        "system_prompt": "你是一位数据分析专家，擅长解读数据、发现趋势和提供洞察。请用结构化的方式呈现分析结果。"
    },
    "translator": {
        "name": "翻译官",
        "description": "精通把英语转换为中文",
        "system_prompt": "你是一位专业的中英双语翻译官，擅长将英语准确、自然地转换为地道的中文。翻译时请注意：1. 忠实传达原文含义，不增删、不篡改；2. 根据语境选择最恰当的中文表达，确保译文流畅自然；3. 专业术语保留准确性，必要时可在括号内补充说明；4. 保留原文的语气和风格（正式/口语/学术等）；5. 遇到歧义或多义词时，优先采用最常用或最符合上下文的译法。"
    }
}

# 输出格式配置
OUTPUT_FORMATS = {
    "text": "自然语言",
    "json": "JSON 格式",
    "list": "清单格式",
    "markdown": "Markdown 格式"
}

class ChatService:
    """
    对话服务类 - 封装所有对话相关业务逻辑
    
    属性:
        llm_client: LLM 客户端实例
        max_context_tokens: 最大上下文 token 数限制
    """
    
    def __init__(self):
        """初始化对话服务"""
        self.llm_client = LLMClient()
        self.max_context_tokens = 4096

    def create_conversation(self, model_provider="deepseek", role="default"):
        """
        创建新会话
        
        参数:
            model_provider: 模型提供商（deepseek/qwen），默认为 deepseek
            role: 角色模板名称，默认为 default
        
        返回:
            int: 新创建的会话ID
        
        异常:
            ValueError: 当模型提供商无效时抛出
        """
        # 获取模型信息
        model_info = Config.get_model_info(model_provider)
        if not model_info:
            raise ValueError(f"不支持的模型提供商: {model_provider}")
        
        # 获取角色信息
        role_info = ROLE_TEMPLATES.get(role, ROLE_TEMPLATES["default"])
        
        # 创建会话记录
        conversation_id = create_conversation(
            title="新对话",
            model_provider=model_provider,
            model_name=model_info["model_name"]
        )
        
        # 添加系统提示词到会话
        add_message(conversation_id, "system", role_info["system_prompt"])
        
        return conversation_id

    def delete_conversation(self, conversation_id):
        """
        删除会话
        
        参数:
            conversation_id: 要删除的会话ID
        """
        delete_conversation(conversation_id)

    def get_conversation_list(self):
        """
        获取所有会话列表
        
        返回:
            list: 会话字典列表，按更新时间倒序排列
        """
        return list_conversations()

    def get_conversation_history(self, conversation_id):
        """
        获取会话消息历史
        
        参数:
            conversation_id: 会话ID
        
        返回:
            list: 消息字典列表
        """
        return get_messages(conversation_id)

    def compress_context(self, messages, max_tokens=3000, model_provider=None):
        """
        上下文压缩 - 长对话时自动总结历史
        
        当对话消息过多时，自动总结历史对话并保留最近的消息，
        以避免超出模型上下文窗口限制。
        
        参数:
            messages: 原始消息列表
            max_tokens: 最大 token 数限制
            model_provider: 模型提供商，默认为当前会话的模型
        
        返回:
            list: 压缩后的消息列表
        """
        # 如果消息数量较少，不需要压缩
        if len(messages) <= 3:
            return messages
        
        # 分离系统提示词和普通消息
        system_prompt = next((m for m in messages if m["role"] == "system"), None)
        recent_messages = messages[-10:]  # 保留最近10条消息
        
        # 构建总结提示词
        summary_prompt = """请总结以下对话历史，保留关键信息：

{conversation}

总结要求：
1. 保留用户的核心问题和关注点
2. 保留已提供的关键答案要点
3. 语言简洁，不超过200字
"""
        
        # 提取需要总结的历史消息
        conversation_text = "\n".join([f"{m['role']}: {m['content'][:200]}" for m in messages[:-10]])
        summary_prompt = summary_prompt.format(conversation=conversation_text)
        
        # 使用传入的模型提供商，或默认使用 deepseek
        provider = model_provider or "deepseek"
        
        # 调用模型生成总结
        model_info = Config.get_model_info(provider)
        client = self.llm_client.create_client_for_provider(provider)
        
        summary = ""
        for chunk in client.chat(
            messages=[{"role": "user", "content": summary_prompt}],
            model=model_info["model_name"],
            temperature=0.3,  # 低温度保证总结准确性
            max_tokens=200
        ):
            summary += chunk
        
        # 构建压缩后的消息列表
        compressed_messages = []
        if system_prompt:
            compressed_messages.append(system_prompt)
        
        # 添加总结作为系统消息
        compressed_messages.append({
            "role": "system",
            "content": f"对话总结：{summary}\n\n---\n以下是最近的对话："
        })
        
        # 添加最近的消息
        compressed_messages.extend(recent_messages)
        
        return compressed_messages

    def validate_json_output(self, response):
        """
        验证 JSON 输出格式是否正确
        
        参数:
            response: 模型响应内容
        
        返回:
            tuple: (is_valid, error_message)
                   is_valid: 布尔值，是否有效
                   error_message: 错误信息，验证通过时为 None
        """
        import json
        import re
        
        # 清理响应内容，去除前后的空白字符和换行
        cleaned_response = response.strip()
        
        # 检查是否为空
        if not cleaned_response:
            return False, "响应内容为空"
        
        # 尝试直接解析
        try:
            json.loads(cleaned_response)
            return True, None
        except json.JSONDecodeError:
            pass
        
        # 如果直接解析失败，尝试从响应中提取 JSON
        # 查找第一个 { 或 [ 到最后一个 } 或 ] 之间的内容
        json_match = re.search(r'(\{.*\}|\[.*\])', cleaned_response, re.DOTALL)
        if json_match:
            extracted_json = json_match.group(1)
            try:
                json.loads(extracted_json)
                return True, None
            except json.JSONDecodeError as e:
                return False, f"提取的 JSON 解析失败: {str(e)}"
        
        # 如果提取也失败，返回原始错误
        try:
            json.loads(cleaned_response)
            return True, None
        except json.JSONDecodeError as e:
            return False, str(e)

    def detect_hallucination(self, response, messages, model_provider=None):
        """
        幻觉检测 - 分析回答是否包含虚构信息
        
        使用大模型检测回答中是否存在幻觉，通过分析：
        1. 是否有明显不符合常识的内容
        2. 是否存在可能的虚构信息
        3. 是否有未经验证的断言
        
        参数:
            response: 模型响应内容
            messages: 对话消息历史
            model_provider: 模型提供商，默认为当前会话的模型
        
        返回:
            tuple: (detected, reason)
                   detected: 布尔值，是否检测到幻觉
                   reason: 检测结果说明
        """
        # 短内容跳过检测
        if len(response) < 50:
            return False, "内容较短，跳过检测"
        
        # 使用传入的模型提供商，或默认使用 deepseek
        provider = model_provider or "deepseek"
        
        # 构建检测提示词
        fact_check_prompt = f"""请分析以下AI回答是否可能包含幻觉（虚构信息）：

用户问题：{messages[-1]['content'][:300] if messages else '无'}

AI回答：{response[:500]}

请判断：
1. 回答中是否有明显不符合常识的内容？
2. 是否存在可能的虚构信息？
3. 是否有未经验证的断言？

请严格按以下格式输出，第一行只能是下面三个标签之一：
[无] 未发现可疑内容
[疑似] 有可疑迹象但无法确认
[是] 明显存在幻觉

第二行开始简要说明理由。
"""
        
        # 调用模型进行检测
        model_info = Config.get_model_info(provider)
        client = self.llm_client.create_client_for_provider(provider)
        
        result = ""
        for chunk in client.chat(
            messages=[{"role": "user", "content": fact_check_prompt}],
            model=model_info["model_name"],
            temperature=0.1,  # 低温度保证判断一致性
            max_tokens=150
        ):
            result += chunk
        
        # 判断检测结果
        first_line = result.strip().splitlines()[0] if result.strip() else ""
        if first_line.startswith("[是]") or first_line.startswith("[疑似]"):
            return True, result
        return False, result

    def build_prompt(self, role, output_format):
        """
        构建完整的系统提示词
        
        根据角色和输出格式构建系统提示词，指导模型生成符合要求的回答。
        
        参数:
            role: 角色模板名称
            output_format: 输出格式（text/json/markdown/list）
        
        返回:
            str: 完整的系统提示词
        """
        # 根据输出格式添加格式指令
        format_instructions = ""
        if output_format == "json":
            format_instructions = "\n\n【重要】你必须以严格的JSON格式输出结果，只输出JSON内容，不要包含任何其他文本、解释或标记。"
        elif output_format == "list":
            format_instructions = "\n\n【重要】你必须使用清单格式输出，每条内容用数字序号（1. 2. 3.）开头，每条内容单独一行。"
        elif output_format == "markdown":
            format_instructions = "\n\n【重要】你必须使用Markdown格式输出，合理使用标题（# ## ###）、加粗（**）、斜体（*）、代码块（```）、列表（- 或 1.）等Markdown语法组织内容。"
        
        # 获取角色的系统提示词并拼接格式指令
        role_info = ROLE_TEMPLATES.get(role, ROLE_TEMPLATES["default"])
        return role_info["system_prompt"] + format_instructions

    def send_message(self, conversation_id, user_content, model_params=None, role="default", output_format="text", model_provider=None):
        """
        发送消息并获取响应（核心方法）
        
        完整的消息处理流程：
        1. 保存用户消息到数据库
        2. 构建完整的消息上下文
        3. 长对话时压缩上下文
        4. 调用大模型获取响应（流式）
        5. JSON格式输出时验证格式
        6. 检测幻觉内容
        7. 保存助手响应到数据库
        8. 更新会话标题（首次消息时）
        
        参数:
            conversation_id: 会话ID
            user_content: 用户输入内容
            model_params: 模型参数字典（可选）
            role: 角色模板名称，默认为 default
            output_format: 输出格式，默认为 text
            model_provider: 模型提供商，如果提供则更新会话的模型配置
        
        返回:
            generator: 流式返回响应内容，每次返回 {"content": str, "hallucination_detected": bool, "hallucination_reason": str}
        
        异常:
            ValueError: 当会话不存在时抛出
        """
        # 验证会话存在
        conversation = get_conversation_by_id(conversation_id)
        if not conversation:
            raise ValueError("会话不存在")

        # 如果提供了新的模型提供商，更新会话的模型配置
        if model_provider and model_provider != conversation["model_provider"]:
            model_info = Config.get_model_info(model_provider)
            if model_info:
                update_conversation_model(conversation_id, model_provider, model_info["model_name"])
                conversation = get_conversation_by_id(conversation_id)
                print(f" 模型已切换: {model_provider} - {model_info['model_name']}")

        # 保存用户消息
        add_message(conversation_id, "user", user_content)

        # 获取当前会话的所有消息
        messages = get_messages(conversation_id)
        
        # 构建系统提示词（使用最新的角色和格式设置）
        system_prompt = self.build_prompt(role, output_format)
        
        # 构建发送给模型的消息列表，只保留一个系统提示词（最新的）
        formatted_messages = [{"role": "system", "content": system_prompt}]
        
        for msg in messages:
            # 跳过所有系统消息（只使用最新构建的系统提示词）
            if msg["role"] != "system":
                formatted_messages.append({"role": msg["role"], "content": msg["content"]})
        
        # 长对话时进行上下文压缩
        if len(formatted_messages) > 15:
            formatted_messages = self.compress_context(
                formatted_messages, 
                model_provider=conversation["model_provider"]
            )

        # 使用默认参数或用户提供的参数
        if not model_params:
            model_params = Config.get_default_params()

        # 获取对应提供商的客户端
        provider_client = self.llm_client.create_client_for_provider(conversation["model_provider"])
        
        # 打印调试信息，显示当前使用的模型和参数
        print(f"\n{'='*50}")
        print(f"当前使用模型: {conversation['model_provider']} - {conversation['model_name']}")
        print(f"Base URL: {provider_client.base_url}")
        print(f"输出格式: {output_format}")
        print(f"Temperature: {model_params.get('temperature', 'N/A')}")
        print(f"Top P: {model_params.get('top_p', 'N/A')}")
        print(f"Max Tokens: {model_params.get('max_tokens', 'N/A')}")
        print(f"{'='*50}\n")
        
        # 流式获取模型响应
        full_response = ""
        response_chunks = []
        for chunk in provider_client.chat(
            messages=formatted_messages,
            model=conversation["model_name"],
            **model_params
        ):
            response_chunks.append(chunk)
            full_response = "".join(response_chunks)
            # 流式返回当前累积的响应
            yield {"content": full_response, "hallucination_detected": False, "hallucination_reason": None}

        # 确保 full_response 包含所有内容
        full_response = "".join(response_chunks).strip()
        
        # JSON格式输出验证
        if output_format == "json":
            # 检查响应是否为空
            if not full_response:
                error_msg = "模型返回空响应，请重试"
                yield {"content": f"JSON格式错误: {error_msg}\n\n原始响应为空", "hallucination_detected": False, "hallucination_reason": None}
                add_message(conversation_id, "assistant", error_msg)
                return
            
            is_valid, error = self.validate_json_output(full_response)
            if not is_valid:
                # 返回格式错误信息
                yield {"content": f"JSON格式错误: {error}\n\n原始响应:\n{full_response}", "hallucination_detected": False, "hallucination_reason": None}
                add_message(conversation_id, "assistant", full_response)
                return

        # 幻觉检测
        hallucination_detected, hallucination_reason = self.detect_hallucination(
            full_response, 
            formatted_messages,
            model_provider=conversation["model_provider"]
        )
        
        if hallucination_detected:
            # 添加幻觉警告
            full_response = f"⚠️ 检测到可能的幻觉内容：\n\n{hallucination_reason}\n\n---\n\n{full_response}"
            yield {"content": full_response, "hallucination_detected": True, "hallucination_reason": hallucination_reason}

        # 保存助手响应
        add_message(conversation_id, "assistant", full_response)

        # 更新会话标题（首次消息时）
        if conversation["title"] == "新对话" and user_content:
            # 取用户消息前10个字作为标题
            title = user_content[:10].strip()
            
            # 如果消息超过10字，添加省略号
            if len(user_content) > 10:
                title = title + "..."
            
            # 检查是否存在相同标题的会话，若有则添加数字后缀
            existing_titles = [conv["title"] for conv in self.get_conversation_list() if conv["id"] != conversation_id]
            original_title = title
            counter = 1
            while title in existing_titles:
                counter += 1
                title = f"{original_title} ({counter})"
            
            update_conversation_title(conversation_id, title)
            print(f" 会话标题已更新: {title}")

    def get_available_models(self):
        """
        获取可用的模型提供商列表
        
        返回:
            list: 模型提供商名称列表
        """
        return Config.get_available_models()

    def get_available_roles(self):
        """
        获取可用的角色模板列表
        
        返回:
            dict: 角色名称映射字典 {key: name}
        """
        return {key: value["name"] for key, value in ROLE_TEMPLATES.items()}

    def get_available_output_formats(self):
        """
        获取可用的输出格式列表
        
        返回:
            dict: 输出格式映射字典
        """
        return OUTPUT_FORMATS

    def get_conversation_by_id(self, conversation_id):
        """
        根据ID获取会话详情
        
        参数:
            conversation_id: 会话ID
        
        返回:
            dict: 会话详情字典，不存在时返回 None
        """
        return get_conversation_by_id(conversation_id)

    def get_role_info(self, role_key):
        """
        获取角色模板详情
        
        参数:
            role_key: 角色模板键名
        
        返回:
            dict: 角色模板信息，包含 name、description、system_prompt
        """
        return ROLE_TEMPLATES.get(role_key, ROLE_TEMPLATES["default"])
