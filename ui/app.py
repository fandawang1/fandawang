"""
UI 模块 - Gradio 界面定义

本模块定义了对话助手的前端界面，包括：
- 会话列表展示
- 聊天界面（消息气泡）
- 模型选择下拉框
- 角色选择下拉框
- 输出格式选择下拉框
- 模型参数调节滑块
- 新建/删除会话按钮

使用 Gradio 5.x 构建，采用组件事件绑定实现交互。
"""

import gradio as gr
from chat_service import ChatService
from config import Config

# 初始化对话服务实例
chat_service = ChatService()

# 当前选中的会话ID
current_conversation_id = None


def load_conversation_list():
    """
    加载会话列表
    
    返回:
        tuple: (choices, value)
               choices: 会话列表，格式为 [(title, id), ...]
               value: 当前选中的值（第一个会话ID或None）
    """
    conversations = chat_service.get_conversation_list()
    choices = [(conv["title"], conv["id"]) for conv in conversations]
    value = choices[0][1] if choices else None
    return choices, value


def load_conversation_history(conversation_id):
    """
    加载指定会话的消息历史
    
    参数:
        conversation_id: 会话ID
    
    返回:
        list: 消息列表，格式为 OpenAI 风格的消息字典列表
    """
    global current_conversation_id
    current_conversation_id = conversation_id
    
    messages = chat_service.get_conversation_history(conversation_id)
    # 转换为 Gradio Chatbot 组件期望的格式
    chatbot_messages = []
    for msg in messages:
        if msg["role"] == "user":
            chatbot_messages.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "assistant":
            chatbot_messages.append({"role": "assistant", "content": msg["content"]})
    
    return chatbot_messages


def create_new_conversation(model_provider, role):
    """
    创建新会话
    
    参数:
        model_provider: 模型提供商（deepseek/qwen）
        role: 角色模板名称
    
    返回:
        tuple: (chatbot, dropdown_update)
               chatbot: 清空的聊天界面
               dropdown_update: 使用 gr.update 更新下拉框的 choices 和 value
    """
    global current_conversation_id
    
    # 创建新会话
    conversation_id = chat_service.create_conversation(
        model_provider=model_provider,
        role=role
    )
    
    current_conversation_id = conversation_id
    
    # 重新加载会话列表，确保包含新创建的会话
    choices, _ = load_conversation_list()
    
    # 使用 gr.update 正确更新下拉框的 choices 和 value
    return [], gr.update(choices=choices, value=conversation_id)


def delete_selected_conversation(conversation_id):
    """
    删除选中的会话
    
    参数:
        conversation_id: 要删除的会话ID
    
    返回:
        tuple: (chatbot, dropdown_update)
               chatbot: 清空的聊天界面
               dropdown_update: 使用 gr.update 更新下拉框的 choices 和 value
    """
    global current_conversation_id
    
    if conversation_id:
        chat_service.delete_conversation(conversation_id)
        
        # 如果删除的是当前会话，重置当前会话ID
        if current_conversation_id == conversation_id:
            current_conversation_id = None
    
    # 重新加载会话列表
    choices, value = load_conversation_list()
    
    # 使用 gr.update 正确更新下拉框的 choices 和 value
    return [], gr.update(choices=choices, value=value)


def send_message(message, history, temperature, top_p, max_tokens, role, output_format, model_provider):
    """
    发送消息并获取响应（流式）
    
    参数:
        message: 用户输入内容
        history: 消息历史列表
        temperature: 采样温度
        top_p: 核采样参数
        max_tokens: 最大生成 token 数
        role: 角色模板名称
        output_format: 输出格式
        model_provider: 模型提供商（deepseek/qwen）
    
    返回:
        generator: 流式返回更新后的历史记录
    """
    global current_conversation_id
    
    # 如果没有当前会话，创建一个新会话
    if not current_conversation_id:
        current_conversation_id = chat_service.create_conversation(
            model_provider=model_provider,
            role=role
        )
    
    # 防御性检查：验证当前会话是否真实存在
    conversation = chat_service.get_conversation_by_id(current_conversation_id)
    if not conversation:
        # 会话不存在，重置并创建新会话
        current_conversation_id = chat_service.create_conversation(
            model_provider=model_provider,
            role=role
        )
    
    # 构建模型参数
    model_params = {
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "stream": True
    }
    
    # 发送消息并获取响应（传入 model_provider 以支持模型切换）
    response = ""
    for chunk in chat_service.send_message(
        conversation_id=current_conversation_id,
        user_content=message,
        model_params=model_params,
        role=role,
        output_format=output_format,
        model_provider=model_provider
    ):
        response = chunk["content"]
        # 更新历史记录
        new_history = history + [{"role": "user", "content": message}, {"role": "assistant", "content": response}]
        yield "", new_history


def get_role_description(role_key):
    """
    获取角色描述
    
    参数:
        role_key: 角色模板键名
    
    返回:
        str: 角色描述信息
    """
    role_info = chat_service.get_role_info(role_key)
    return f"角色描述: {role_info['description']}"


def build_app():
    """
    构建 Gradio 应用界面
    
    返回:
        gr.Blocks: Gradio 应用实例
    """
    with gr.Blocks(title="大模型对话助手") as demo:
        # 设置页面标题
        gr.Markdown("# 🤖 大模型对话助手")
        
        # 主布局：左右分栏
        with gr.Row():
            # 左侧：会话列表
            with gr.Column(scale=1):
                gr.Markdown("## 会话列表")
                
                # 初始化会话列表
                conv_choices, conv_value = load_conversation_list()
                
                # 会话列表下拉框
                conversation_dropdown = gr.Dropdown(
                    choices=conv_choices,
                    value=conv_value,
                    label="选择会话",
                    info="选择历史会话继续对话",
                    allow_custom_value=True  # 允许自定义值，解决更新时序问题
                )
                
                # 新建会话按钮
                with gr.Row():
                    new_btn = gr.Button("新建对话", variant="primary")
                    refresh_btn = gr.Button("刷新列表", variant="primary")
                
                # 删除会话按钮
                delete_btn = gr.Button("删除会话", variant="primary")
                
                # 角色选择
                role_dropdown = gr.Dropdown(
                    choices=[(name, key) for key, name in chat_service.get_available_roles().items()],
                    value="default",
                    label="角色设定",
                    info="选择助手角色"
                )
                
                # 角色描述显示
                role_description = gr.Markdown(
                    value=get_role_description("default"),
                    label="角色描述"
                )
            
            # 右侧：聊天区域
            with gr.Column(scale=3):
                # 聊天界面
                chatbot = gr.Chatbot(
                    label="对话"
                )
                
                # 用户输入框
                msg_input = gr.Textbox(
                    label="输入消息",
                    placeholder="请输入您的问题...",
                    lines=2
                )
                
                # 发送按钮
                send_btn = gr.Button("发送", variant="primary")
                
                # 参数设置区域
                with gr.Accordion("参数设置", open=False):
                    with gr.Row():
                        # 模型选择
                        model_dropdown = gr.Dropdown(
                            choices=[("DeepSeek", "deepseek"), ("Qwen", "qwen")],
                            value=Config.PROVIDER,
                            label="选择模型",
                            info="选择对话使用的大模型"
                        )
                        
                        # 输出格式选择
                        output_format_dropdown = gr.Dropdown(
                            choices=[(name, key) for key, name in chat_service.get_available_output_formats().items()],
                            value="text",
                            label="输出格式",
                            info="text=自然语言, json=JSON格式, list=清单格式"
                        )
                    
                    # 温度调节
                    temperature_slider = gr.Slider(
                        minimum=0.0,
                        maximum=2.0,
                        value=Config.TEMPERATURE,
                        step=0.1,
                        label="Temperature",
                        info="采样温度，值越高输出越随机"
                    )
                    
                    # top_p 调节
                    top_p_slider = gr.Slider(
                        minimum=0.0,
                        maximum=1.0,
                        value=Config.TOP_P,
                        step=0.05,
                        label="Top P",
                        info="核采样参数，控制采样范围"
                    )
                    
                    # max_tokens 调节
                    max_tokens_slider = gr.Slider(
                        minimum=128,
                        maximum=8192,
                        value=Config.MAX_TOKENS,
                        step=128,
                        label="Max Tokens",
                        info="最大生成 token 数"
                    )
        
        # ==================== 事件绑定 ====================
        
        # 选择会话时加载历史记录
        conversation_dropdown.change(
            fn=load_conversation_history,
            inputs=[conversation_dropdown],
            outputs=[chatbot]
        )
        
        # 新建会话按钮点击
        new_btn.click(
            fn=create_new_conversation,
            inputs=[model_dropdown, role_dropdown],
            outputs=[chatbot, conversation_dropdown]
        )
        
        # 刷新会话列表按钮点击
        def refresh_list():
            choices, value = load_conversation_list()
            return gr.update(choices=choices, value=value)
        
        refresh_btn.click(
            fn=refresh_list,
            inputs=[],
            outputs=[conversation_dropdown]
        )
        
        # 删除会话按钮点击
        delete_btn.click(
            fn=delete_selected_conversation,
            inputs=[conversation_dropdown],
            outputs=[chatbot, conversation_dropdown]
        )
        
        # 发送消息（点击按钮）
        send_btn.click(
            fn=send_message,
            inputs=[
                msg_input,
                chatbot,
                temperature_slider,
                top_p_slider,
                max_tokens_slider,
                role_dropdown,
                output_format_dropdown,
                model_dropdown
            ],
            outputs=[msg_input, chatbot]
        )
        
        # 发送消息（按回车键）
        msg_input.submit(
            fn=send_message,
            inputs=[
                msg_input,
                chatbot,
                temperature_slider,
                top_p_slider,
                max_tokens_slider,
                role_dropdown,
                output_format_dropdown,
                model_dropdown
            ],
            outputs=[msg_input, chatbot]
        )
        
        # 角色选择变化时更新角色描述
        role_dropdown.change(
            fn=get_role_description,
            inputs=[role_dropdown],
            outputs=[role_description]
        )
    
    return demo
