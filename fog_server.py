import logging

logger = logging.getLogger('ComfyFog')

from . import fog_manager

def fog_status(req):
    """
    获取Fog节点当前状态
    
    请求方式：GET /fog/status
    
    Returns:
        {
            "status": {
                "enabled": bool,        # 是否启用
                "connected": bool,      # 是否连接到任务中心
                "scheduler_active": bool,  # 调度器是否活跃
                "current_task": {       # 当前任务信息，无任务时为null
                    "id": str,          # 任务ID
                    "status": str,      # 任务状态：processing/completed/failed
                    "started_at": str,  # 开始时间，ISO格式
                    "progress": float   # 进度，0-1
                },
                "schedule": [           # 调度时间段列表
                    {
                        "start": str,   # 开始时间，格式 "HH:MM"
                        "end": str      # 结束时间，格式 "HH:MM"
                    }
                ]
            }
        }
    """
    try:
        return {"status": fog_manager.get_status()}
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return {"status": "error", "message": str(e)}

def fog_update_config(req):
    """
    更新Fog节点配置
    
    请求方式：POST /fog/config
    
    请求体：
    {
        "enabled": bool,               # 可选，是否启用
        "task_center_url": str,        # 可选，任务中心URL
        "schedule": [                  # 可选，调度时间段
            {
                "start": str,          # 开始时间，格式 "HH:MM"
                "end": str            # 结束时间，格式 "HH:MM"
            }
        ],
        "max_tasks_per_day": int,     # 可选，每日最大任务数
        "min_gpu_memory": int,        # 可选，最小GPU内存要求(MB)
        "retry_interval": int,        # 可选，重试间隔(秒)
        "max_retries": int           # 可选，最大重试次数
    }
    
    Returns:
        成功：
        {
            "status": "success"
        }
        
        失败：
        {
            "status": "error",
            "message": str            # 错误信息
        }
    """
    try:
        if not req.json:
            raise ValueError("Request body is empty")
        return fog_manager.update_config(req.json)
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return {"status": "error", "message": str(e)}


# ComfyUI路由定义
ROUTES = [
    ("fog/status", fog_status),                    # GET 获取状态
    ("fog/config", fog_update_config, ["POST"]),   # POST 更新配置

]

# 导出必要的变量
__all__ = ['ROUTES']