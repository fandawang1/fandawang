"""
应用入口文件 - 启动大模型对话助手

本文件是应用的入口点，负责：
1. 验证配置有效性
2. 初始化数据库
3. 启动 Gradio 应用
"""

from config import Config
from database import init_database
from ui.app import build_app


def main():
    """
    主函数 - 应用启动入口
    
    执行流程:
    1. 验证配置文件（.env）中的参数是否有效
    2. 如果配置验证失败，输出错误信息并退出
    3. 初始化 SQLite 数据库
    4. 构建并启动 Gradio 应用
    """
    # 验证配置
    errors = Config.validate()
    if errors:
        print("[ERROR] 配置验证失败:")
        for error in errors:
            print(f"  - {error}")
        print("\n请检查 .env 文件配置是否正确")
        return

    # 初始化数据库
    init_database()
    
    # 输出启动信息
    print("[OK] 数据库初始化成功")
    print("[START] 启动 Gradio 应用...")
    
    # 构建并启动应用
    demo = build_app()
    demo.launch(
        server_name="127.0.0.1",  # 允许外部访问
        server_port=7860,        # 默认端口
        share=False,             # 不生成共享链接
        debug=True               # 启用调试模式
    )


if __name__ == "__main__":
    """
    Python 脚本入口
    
    当脚本直接运行时执行 main() 函数
    """
    main()
