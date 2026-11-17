"""
数据库模块 - 负责对话数据的持久化存储

本模块使用 SQLite 数据库存储会话和消息数据，
提供完整的 CRUD 操作封装，支持会话管理和历史记录查询。
"""

import sqlite3
import os
from datetime import datetime

# 数据库文件路径：项目根目录下的 data/chat.db
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "data", "chat.db")

def init_database():
    """
    初始化数据库 - 创建必要的表结构
    
    创建 conversations（会话表）和 messages（消息表），
    如果表已存在则不做操作。
    """
    # 确保 data 目录存在
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    
    # 建立数据库连接
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # 启用外键约束，确保级联删除生效
    cursor = conn.cursor()
    
    # 创建会话表
    # 字段说明:
    #   id: 主键，自增
    #   title: 会话标题
    #   model_provider: 模型提供商（deepseek/qwen）
    #   model_name: 使用的模型名称
    #   created_at: 创建时间
    #   updated_at: 最后更新时间
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT '新对话',
            model_provider TEXT NOT NULL,
            model_name TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建消息表
    # 字段说明:
    #   id: 主键，自增
    #   conversation_id: 关联的会话ID（外键）
    #   role: 角色（user/assistant/system）
    #   content: 消息内容
    #   created_at: 创建时间
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    ''')
    
    # 提交更改并关闭连接
    conn.commit()
    conn.close()


def create_conversation(title="新对话", model_provider="deepseek", model_name=""):
    """
    创建新会话
    
    参数:
        title: 会话标题，默认为"新对话"
        model_provider: 模型提供商，默认为"deepseek"
        model_name: 模型名称
    
    返回:
        int: 新创建的会话ID
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # 启用外键约束
    cursor = conn.cursor()
    
    # 对于"新对话"这种临时名称，直接创建，不添加数字后缀
    # 对于其他名称，检查是否存在相同标题的会话，若有则添加数字后缀
    if title != "新对话":
        original_title = title
        counter = 1
        while True:
            cursor.execute('SELECT COUNT(*) FROM conversations WHERE title = ?', (title,))
            count = cursor.fetchone()[0]
            if count == 0:
                break
            counter += 1
            title = f"{original_title} ({counter})"
    
    # 插入新会话记录
    cursor.execute(
        '''INSERT INTO conversations (title, model_provider, model_name, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?)''',
        (title, model_provider, model_name, datetime.now(), datetime.now())
    )
    
    # 获取自增的会话ID
    conversation_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return conversation_id


def delete_conversation(conversation_id):
    """
    删除会话及其关联的所有消息
    
    参数:
        conversation_id: 要删除的会话ID
    
    说明:
        由于 messages 表设置了 ON DELETE CASCADE，
        删除会话时会自动删除关联的消息
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # 启用外键约束，确保级联删除生效
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM conversations WHERE id = ?', (conversation_id,))
    conn.commit()
    conn.close()


def list_conversations():
    """
    获取所有会话列表
    
    返回:
        list: 会话字典列表，按更新时间倒序排列
              每个字典包含 id, title, model_provider, model_name, created_at, updated_at
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # 启用外键约束
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, title, model_provider, model_name, created_at, updated_at
        FROM conversations
        ORDER BY updated_at DESC
    ''')
    
    conversations = []
    for row in cursor.fetchall():
        conversations.append({
            "id": row[0],
            "title": row[1],
            "model_provider": row[2],
            "model_name": row[3],
            "created_at": row[4],
            "updated_at": row[5]
        })
    
    conn.close()
    return conversations


def get_messages(conversation_id):
    """
    获取指定会话的所有消息
    
    参数:
        conversation_id: 会话ID
    
    返回:
        list: 消息字典列表，按创建时间正序排列
              每个字典包含 role, content, created_at
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # 启用外键约束
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT role, content, created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY created_at ASC
    ''', (conversation_id,))
    
    messages = []
    for row in cursor.fetchall():
        messages.append({
            "role": row[0],
            "content": row[1],
            "created_at": row[2]
        })
    
    conn.close()
    return messages


def add_message(conversation_id, role, content):
    """
    添加新消息到会话
    
    参数:
        conversation_id: 会话ID
        role: 角色（user/assistant/system）
        content: 消息内容
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # 启用外键约束
    cursor = conn.cursor()
    
    # 插入消息记录
    cursor.execute(
        '''INSERT INTO messages (conversation_id, role, content, created_at)
           VALUES (?, ?, ?, ?)''',
        (conversation_id, role, content, datetime.now())
    )
    
    # 更新会话的更新时间
    cursor.execute(
        '''UPDATE conversations SET updated_at = ? WHERE id = ?''',
        (datetime.now(), conversation_id)
    )
    
    conn.commit()
    conn.close()


def update_conversation_title(conversation_id, title):
    """
    更新会话标题
    
    参数:
        conversation_id: 会话ID
        title: 新标题
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # 启用外键约束
    cursor = conn.cursor()
    
    cursor.execute(
        '''UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?''',
        (title, datetime.now(), conversation_id)
    )
    
    conn.commit()
    conn.close()


def update_conversation_model(conversation_id, model_provider, model_name):
    """
    更新会话的模型配置
    
    参数:
        conversation_id: 会话ID
        model_provider: 模型提供商
        model_name: 模型名称
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # 启用外键约束
    cursor = conn.cursor()
    
    cursor.execute(
        '''UPDATE conversations SET model_provider = ?, model_name = ?, updated_at = ? WHERE id = ?''',
        (model_provider, model_name, datetime.now(), conversation_id)
    )
    
    conn.commit()
    conn.close()


def get_conversation_by_id(conversation_id):
    """
    根据ID获取会话详情
    
    参数:
        conversation_id: 会话ID
    
    返回:
        dict: 会话详情字典，包含 id, title, model_provider, model_name, created_at, updated_at
              如果会话不存在返回 None
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # 启用外键约束
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, title, model_provider, model_name, created_at, updated_at
        FROM conversations
        WHERE id = ?
    ''', (conversation_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row[0],
            "title": row[1],
            "model_provider": row[2],
            "model_name": row[3],
            "created_at": row[4],
            "updated_at": row[5]
        }
    return None
