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
        if not self.is_in_schedule():
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
         
        try:
            # 4.1 提交任务到ComfyUI并获取prompt_id
            self.current_task_id = self.current_task.get("task_id")
            self.current_workflow = self.current_task.get("workflow")                   
            logger.debug(f"Task submitted to ComfyUI, task_id: {self.current_task_id}, workflow: {self.current_workflow}")

            result = self.comfy_client.submit_workflow(self.current_workflow)
            
            if not result["success"]:
                raise Exception(result["error"])
            
            self.current_prompt_id = result['prompt_id']                
            logger.debug(f"Task prompt_queue success, task_id: {self.current_task_id }, prompt_id: {self.current_prompt_id}")

            
            # 4.2 等待任务完成并获取结果
            images = self.comfy_client.wait_websock_result(self.current_prompt_id)            
            logger.debug(f"Task completed ,  task_id: {self.current_task_id }, prompt_id: {self.current_prompt_id}, image:{images}")
 

            """
            # 4.3 处理图片文件并准备提交数据
            processed_result = self._process_images(result)
            
            # 4.4 提交结果
            submission_data = {
                "task_id": self.current_task_id,
                "output": processed_result,
                "status": "completed",
                "completed_at": datetime.now().isoformat()
            }
            self.fog_client.submit_result(submission_data)
            
    
            """

        except Exception as e:
            logger.error(f"ComyFog processing loop error: {e}")
            logger.error(traceback.format_exc())  # 打印完整堆栈
            error_data = {
                "task_id": self.current_task_id,
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.now().isoformat()
            }
            self.fog_client.submit_result(error_data)
            self._record_history(self.current_task, "failed", str(e))
            
        finally:
            self.current_prompt_id = None
            self.current_task_id = None
            self.current_task = None



    def _process_images(self, result):
        """处理结果中的图片文件"""
        try:
            import folder_paths  # ComfyUI的路径处理模块
            
            processed_result = {
                "images": [],
                "node_outputs": result  # 保留原始节点输出信息
            }
            
            # 获取ComfyUI的输出目录
            output_dir = folder_paths.get_output_directory()
            
            # 遍历所有节点的输出
            for node_id, node_output in result.items():
                if "images" in node_output:
                    for img_info in node_output["images"]:
                        # 构建完整的图片路径
                        subfolder = img_info.get("subfolder", "")
                        filename = img_info["filename"]
                        image_path = os.path.join(output_dir, subfolder, filename)
                        
                        if os.path.exists(image_path):
                            # 读取图片文件并转换为base64
                            with open(image_path, "rb") as img_file:
                                img_data = base64.b64encode(img_file.read()).decode()
                                
                                # 添加到处理后的结果中
                                processed_result["images"].append({
                                    "data": img_data,
                                    "filename": filename,
                                    "node_id": node_id,
                                    "type": img_info.get("type", "output")
                                })
                                
                            logger.info(f"Processed image {filename} from node {node_id}")
                        else:
                            logger.warning(f"Image file not found: {image_path}")
            
            return processed_result
            
        except Exception as e:
            logger.error(f"Error processing images: {e}")
            raise

    def is_in_schedule(self) -> bool:
        """检查当前时间是否在调度时间内"""
        if not self.schedule:
            return True  # 没有设置调度时间时默认允许执行
            
        current_time = datetime.now().strftime("%H:%M")
        for slot in self.schedule:
            if slot['start'] <= current_time <= slot['end']:
                return True
        return False


