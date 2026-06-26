"""
共享限流器实例（供 main.py 注册和路由装饰器使用）
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
