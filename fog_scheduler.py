import sys
import os
import json
import time
import logging
import base64
import websocket
import threading
import traceback  # 导入 traceback 模块

from typing import Optional
from datetime import datetime
from queue import Queue, Empty

from .fog_client import FogClient
from .fog_comfy import ComfyUIClient


# 获取 ComfyUI 的路径
COMFY_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if COMFY_PATH not in sys.path:
    sys.path.append(COMFY_PATH)

# 正确导入 ComfyUI 的模块
from execution import PromptQueue
from server import PromptServer

logger = logging.getLogger('ComfyFog')

class FogScheduler:
    """
    任务调度器
    负责任务的执行、监控和结果处理
    """
    def __init__(self, fog_client: FogClient):
        """
        初始化FogScheduler
        
        Args:
            fog_client (FogClient): FogClient实例，用于与任务中心通信
            
        Raises:
            ValueError: 当fog_client为None或类型不正确时
        """
        if not isinstance(fog_client, FogClient):
            raise ValueError("fog_client must be an instance of FogClient")
            
        self.fog_client = fog_client
        self.comfy_client = ComfyUIClient()

        self.current_task: Optional[dict] = None  # 当前在处理的任务
        self.current_prompt_id = None  # 当前正在执行的prompt ID
        self.current_task_id = None  # 当前正在执行的任务ID


        self.schedule = []  # 添加调度时间列表
        
          
            
    def process_task(self):
        """任务处理主流程"""
        # 1. 检查是否在调度时间内
        if not self._is_in_schedule():
            logger.debug("Not in scheduled time")
            return False
            
        # 2. 检查队列状态
        queue_status = self.comfy_client.get_queue_status()
        if  not queue_status["success"]:
            logger.error(f"ComfyQueue status get error : {queue_status['error']}")
            return False;
        if queue_status["queue_remaining"]:
            logger.info(f"ComfyQueue remaining {queue_status['queue_remaining']} task, wait next loop.")
            return False
        logger.info(f"ComfyQueue is idle, {queue_status['queue_remaining']} task, next step")

        # 3. 获取新任务        
        self.current_task = self.fog_client.fetch_task()
        if not self.current_task.get("success"):  
            logger.error(f"{self.current_task.get("error")}")
            return False


        # 4. 处理任务
        self.task_start_time = int(time.time())
        try:
            # 4.1 提交任务到ComfyUI并获取prompt_id
            self.current_task_id = self.current_task.get("task_id")
            self.current_workflow = self.current_task.get("workflow")

            # workflow 校验并上报 缺失插件 或 模型, 校验返回    valid[3]
            """
            {
                '4': {
                    'errors': [{
                        'type': 'value_not_in_list',
                        'message': 'Value not in list',
                        'details': "ckpt_name: 'v1-5-pruned-emaonly-fp16.safetensors' not in []",
                        'extra_info': {
                            'input_name': 'ckpt_name',
                            'input_config': ([], {
                                'tooltip': 'The name of the checkpoint (model) to load.'
                            }),
                            'received_value': 'v1-5-pruned-emaonly-fp16.safetensors'
                        }
                    }],
                    'dependent_outputs': ['9'],
                    'class_type': 'CheckpointLoaderSimple'
                }
            }
            """
            valid = self.comfy_client.validate_prompt(self.current_workflow)
            if not valid[0]:
                logger.error(f"Invalid workflow, {valid}")          
                raise Exception("Invalid workflow: {}".format(valid[1]))
                              
            logger.debug(f"Task submitted to ComfyUI, task_id: {self.current_task_id}, workflow: {self.current_workflow}, create_at: {self.current_task.get("create_at")}")

            result = self.comfy_client.submit_workflow(self.current_workflow)
            
            if not result["success"]:
                raise Exception(result["error"])
            
            self.current_prompt_id = result['prompt_id']                
            logger.debug(f"Task prompt_queue success, task_id: {self.current_task_id }, prompt_id: {self.current_prompt_id}")

            
            # 4.2 等待任务完成并获取结果
            result = self.comfy_client.wait_websock_result(self.current_prompt_id)            
            logger.debug(f"Task interface completed ,  task_id: {self.current_task_id }, prompt_id: {self.current_prompt_id}, resp:{result}")
            if not result["success"]:
                raise Exception(result["error"])
            images = result["images"]
            
            # 4.3 上传图片以及相关meta信息, 失败进队列，后续可重试
   
            meta = {};
            meta["task_id"] = self.current_task_id
            meta["create_at"] = self.current_task.get("create_at")
            meta["start_at"] = self.task_start_time
            meta["end_at"] = int(time.time())
            meta["images_idx"] = ""         #多图索引
            for node, details in images.items():
                files = details.get('file', [])
                for index,file in enumerate(files):
                    meta["images_idx"] += (f"/{node}/{index},")
            
            resp = {}
            ret = self.fog_client.upload_images(meta, images, resp)
            if not ret :
                logger.error(f"Task upload error ,  task_id: {self.current_task_id }, prompt_id: {self.current_prompt_id}, resp:{resp}")
            else:
                logger.info(f"Task upload success ,  task_id: {self.current_task_id }, prompt_id: {self.current_prompt_id}, resp:{resp}")
 
        

        except Exception as e:
            logger.error(f"ComyFog processing loop error: {e}")
            logger.error(traceback.format_exc())  
 
            
        finally:
            self.current_prompt_id = None
            self.current_task_id = None
            self.current_task = None



    def _is_in_schedule(self) -> bool:
        """检查当前时间是否在调度时间内"""
        if not self.schedule:
            return True  # 没有设置调度时间时默认允许执行
            
        current_time = datetime.now().strftime("%H:%M")
        for slot in self.schedule:
            if slot['start'] <= current_time <= slot['end']:
                return True
        return False


