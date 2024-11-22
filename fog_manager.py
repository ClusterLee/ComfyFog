import os
import json
import time
import threading
import logging
from typing import Optional
from .fog_client import FogClient
from .fog_scheduler import FogScheduler

logger = logging.getLogger('ComfyFog')

class FogManager:
    """ComfyFog插件的核心管理类"""
    
    def __init__(self):
        """初始化Fog管理器"""
        try:
            # 1. 初始化配置
            self.config = self._load_config()
            
            # 2. 初始化组件
            self.client = self._init_client()
            self.scheduler = self._init_scheduler()
            
            # 3. 初始化线程安全锁
            self.lock = threading.Lock()
            
            # 4. 启动监控线程
            self.running = True
            self._start_monitor_thread()
            
            
            self.history = []
            self.max_history = 100
            
            logger.info("FogManager initialized successfully")
            
        except Exception as e:
            logger.error(f"FogManager initialization failed: {e}")
            self.running = False
            raise

    def _init_client(self) -> Optional[FogClient]:
        """初始化FogClient"""
        try:
            if not self.config.get('task_center_url'):
                logger.warning("task_center_url not configured")
                return None
            return FogClient(self.config['task_center_url'])
        except Exception as e:
            logger.error(f"Failed to initialize FogClient: {e}")
            return None

    def _init_scheduler(self) -> Optional[FogScheduler]:
        """初始化FogScheduler"""
        if not self.client:
            logger.warning("FogClient not available, scheduler initialization skipped")
            return None
        return FogScheduler(self.client)

    def get_status(self):
        """获取当前状态"""
        with self.lock:
            return {
                "enabled": self.config.get("enabled", False),
                "connected": bool(self.client and self.client.test_connection()),
                "scheduler_active": bool(self.scheduler),
                "current_task": self.scheduler.current_task if self.scheduler else None,
                "schedule": self.config.get("schedule", [])
            }

    def update_config(self, new_config):
        """更新配置"""
        with self.lock:
            try:
                self.config.update(new_config)
                self._save_config()
                
                # 如果URL改变，重新初始化client
                if 'task_center_url' in new_config:
                    self.client = self._init_client()
                    self.scheduler = self._init_scheduler()
                
                return {"status": "success"}
            except Exception as e:
                logger.error(f"Failed to update config: {e}")
                return {"status": "error", "message": str(e)}

    def _start_monitor_thread(self):
        """启动监控线程"""
        def monitor_loop():
            while self.running:
                try:
                    if self.scheduler and self.config.get("enabled"):
                        self.scheduler.process_task()
                except Exception as e:
                    logger.error(f"Error in monitor loop: {e}")
                time.sleep(5)

        self.monitor_thread = threading.Thread(
            target=monitor_loop,
            name="FogMonitor",
            daemon=True
        )
        self.monitor_thread.start()

    def __del__(self):
        """清理资源"""
        try:
            self.running = False
            if hasattr(self, 'monitor_thread'):
                self.monitor_thread.join(timeout=1)
            if hasattr(self, 'client'):
                self.client.session.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def _load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            return {}  # 默认空配置
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}
            
    def _save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def get_history(self, limit: int = 10, status: Optional[str] = None):
        """获取任务历史"""
        filtered_history = self.history
        if status:
            filtered_history = [h for h in filtered_history if h['status'] == status]
        return filtered_history[-limit:]
        
    def clear_history(self):
        """清除历史记录"""
        self.history = []
        