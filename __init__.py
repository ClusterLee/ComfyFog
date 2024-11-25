import os
import logging
import traceback  # 导入 traceback 模块
import logging.handlers

def setup_logger(logger_name: str = 'ComfyFog', log_dir: str = 'logs') -> logging.Logger:
    """
    配置并返回日志记录器
    
    Args:
        logger_name: 日志记录器名称
        log_dir: 日志文件目录
    
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    # 创建日志目录
    log_dir = os.path.join(os.path.dirname(__file__), log_dir)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 配置日志
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    # 添加回滚文件处理器
    log_file = os.path.join(log_dir, f'{logger_name.lower()}.log')
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)

    # 设置日志格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    # 将处理器添加到logger
    logger.addHandler(file_handler)
    
    logger.info(f"{logger_name} logger initialized")
    return logger

# 创建默认的日志记录器
logger = setup_logger()

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