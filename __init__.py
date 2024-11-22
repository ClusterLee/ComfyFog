import os
import sys
import logging

# 创建日志目录
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 配置日志
logger = logging.getLogger('ComfyFog')
logger.setLevel(logging.DEBUG)

# 控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)

# 文件处理器
file_handler = logging.FileHandler(os.path.join(log_dir, 'comfyfog.log'))
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# 添加处理器
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# 测试日志
logger.info("ComfyFog logger initialized")

try:
    # 1. 设置Web目录
    WEB_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
    
    # 确保web目录存在
    if not os.path.exists(WEB_DIRECTORY):
        os.makedirs(WEB_DIRECTORY)
        
    # 2. 导入核心组件
    from .fog_server import ROUTES
    from .fog_manager import FogManager  # 新的管理类

    # 3. 初始化fog管理器
    fog_manager = FogManager()

    # 4. 导出必要的变量
    __all__ = ['WEB_DIRECTORY', 'ROUTES', 'fog_manager']

except Exception as e:
    logger.error(f"Error initializing ComfyFog: {e}")
    WEB_DIRECTORY = ""
    ROUTES = []
