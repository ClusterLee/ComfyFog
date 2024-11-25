import os
import logging
import traceback  # 导入 traceback 模块

# 创建日志目录
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 配置日志
logger = logging.getLogger('ComfyFog')
logger.setLevel(logging.DEBUG)
# 测试日志
logger.info("ComfyFog logger initialized")

try:
    # 1. 设置Web目录
    WEB_DIRECTORY = os.path.join(os.path.dirname(__file__), "web")

    # 确保web目录存在
    if not os.path.exists(WEB_DIRECTORY):
        os.makedirs(WEB_DIRECTORY)
        
    # 2. 导入核心组件
    from .fog_server import ROUTES
    from .fog_manager import FogManager  # 新的管理类

    # 3. 初始化fog管理器
    fog_manager = FogManager()

    logger.info("ComfyFog initialized Success")

    # 4. 定义节点映射
    NODE_CLASS_MAPPINGS = {
        # "节点名称": 节点类
        # 例如:
        # "FogNode": FogNode
    }

    # 可选：添加节点类别映射
    NODE_DISPLAY_NAME_MAPPINGS = {
        # "FogNode": "Fog Node"
    }

    # 5. 导出必要的变量
    __all__ = ['WEB_DIRECTORY', 'ROUTES', 'fog_manager', 'NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']

except Exception as e:
    logger.error(f"Error initializing ComfyFog: {e}")
    logger.error(traceback.format_exc())  # 打印完整堆栈
    raise  