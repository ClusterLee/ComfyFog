import sys
import os
import json
import time
from datetime import datetime
import logging
import base64
import websocket
import threading
from queue import Queue, Empty
from typing import Optional

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
        self.current_task: Optional[dict] = None  # 当前���在处理的任务
        self.task_history = []    # 任务历史记录
        self.max_history = 100
        self.queue_status = {"busy": False, "tasks": 0}
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.ws = None           # WebSocket连接
        self.result_queue = Queue()  # 用于存储WebSocket结果的队列
        self.current_prompt_id = None  # 当前正在执行的prompt ID
        self.schedule = []  # 添加调度时间列表
        
    def check_queue_status(self):
        """检查ComfyUI队列状态"""
        try:
            # 获取当前执行队列
            prompt_queue = PromptQueue.instance.get_current_queue()
            
            # 检查队列状态
            self.queue_status = {
                "busy": prompt_queue.is_running() or not prompt_queue.queue.empty(),
                "tasks": prompt_queue.queue.qsize()
            }
            
            logger.debug(f"Queue status: {self.queue_status}")
            return not self.queue_status["busy"]
            
        except Exception as e:
            logger.error(f"Error checking queue status: {e}")
            return False
            
    def process_task(self):
        """任务处理主流程"""
        # 1. 检查是否在调度时间内
        if not self.is_in_schedule():
            logger.debug("Not in scheduled time")
            return False
            
        # 2. 检查队列状态
        if not self.check_queue_status():
            logger.debug("Queue is busy")
            return False
            
        # 3. 获取新任务
        if not self.current_task:
            self.current_task = self.fog_client.fetch_task()
            
        # 4. 处理任务
        if self.current_task:
            try:
                # 4.1 提交任务到ComfyUI并获取prompt_id
                workflow = self.current_task.get("workflow", {})
                if not workflow:
                    raise ValueError("Empty workflow in task")
                    
                # 使用 PromptServer 执行任务
                prompt_id = PromptServer.instance.prompt_queue.put(workflow)
                if not prompt_id:
                    raise ValueError("Failed to get prompt_id from ComfyUI")
                    
                logger.info(f"Task submitted to ComfyUI, prompt_id: {prompt_id}")
                self.current_prompt_id = prompt_id
                
                # 4.2 建立WebSocket连接
                self._connect_websocket()
                
                # 4.3 等待任务完成并获取结果
                result = self._wait_for_result()
                
                # 4.4 处理图片文件并准备提交数据
                processed_result = self._process_images(result)
                
                # 4.5 提交结果
                submission_data = {
                    "task_id": self.current_task["id"],
                    "output": processed_result,
                    "status": "completed",
                    "completed_at": datetime.now().isoformat()
                }
                self.fog_client.submit_result(submission_data)
                
                # 4.6 记录历史
                self._record_history(self.current_task, "completed", processed_result)
                
            except Exception as e:
                logger.error(f"Error processing task: {e}")
                error_data = {
                    "task_id": self.current_task["id"],
                    "status": "failed",
                    "error": str(e),
                    "completed_at": datetime.now().isoformat()
                }
                self.fog_client.submit_result(error_data)
                self._record_history(self.current_task, "failed", str(e))
                
            finally:
                self.current_prompt_id = None
                self.current_task = None

    def _wait_for_result(self):
        """等待并收集WebSocket结果"""
        results = {
            "images": [],
            "node_outputs": {},
            "prompt_id": self.current_prompt_id
        }
        start_time = time.time()
        MAX_WAIT_TIME = 300  # 5分钟超时
        
        try:
            while (time.time() - start_time) < MAX_WAIT_TIME:
                try:
                    # 使用较短的超时时间，便于检查总体等待时间
                    result_type, data = self.result_queue.get(timeout=1.0)
                    
                    if result_type == 'error':
                        raise Exception(data)
                    elif result_type == 'output':
                        results.update(data)
                        logger.debug(f"Received output from node: {list(data.keys())[0]}")
                    elif result_type == 'completed':
                        logger.info("Task execution completed")
                        return self._process_execution_result(results)
                        
                except Empty:
                    # 每次超时都检查一下WebSocket连接状态
                    if not self._check_websocket_health():
                        raise ConnectionError("WebSocket connection lost")
                    continue
                    
            # 如果超过最大等待时间
            raise TimeoutError(f"Task execution timeout after {MAX_WAIT_TIME} seconds")
            
        except Exception as e:
            logger.error(f"Error waiting for result: {e}")
            raise
            

    def _check_websocket_health(self):
        """检查WebSocket连接状态"""
        try:
            if self.ws and self.ws.connected:
                return True
            logger.warning("WebSocket connection lost, attempting to reconnect")
            self._connect_websocket()
            return self.ws and self.ws.connected
        except Exception as e:
            logger.error(f"Error checking WebSocket health: {e}")
            return False

    def _connect_websocket(self):
        """
        连接到ComfyUI的WebSocket
        用于接收任务执行状态和结果
        """
        try:
            if self.ws is None or not self.ws.connected:
                self.ws = websocket.WebSocketApp(
                    "ws://127.0.0.1:8188/ws",
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )
                self.ws_thread = threading.Thread(target=self.ws.run_forever)
                self.ws_thread.daemon = True
                self.ws_thread.start()
                logger.info("Connected to ComfyUI WebSocket")
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            raise

    def _on_message(self, ws, message):
        """
        处理WebSocket消息
        处理不同型的消息：
        - executing: 任务执行状态
        - executed: 节点输出结果
        - error: 错误信息
        """
        try:
            data = json.loads(message)
            
            # 只处理当前任务的消息
            if not self.current_prompt_id:
                return
                
            if 'type' in data:
                if data['type'] == 'executing':
                    # 任务执行状态更新
                    if data['data']['node'] is None and data['data']['prompt_id'] == self.current_prompt_id:
                        # 整个工作流执行完成
                        logger.info(f"Task {self.current_prompt_id} completed")
                        self.result_queue.put(('completed', None))
                        
                elif data['type'] == 'executed':
                    # 单个节点执行完成
                    if data['data']['prompt_id'] == self.current_prompt_id:
                        node_id = data['data']['node']
                        output = data['data']['output']
                        if output and 'images' in output:
                             # 这里的output['images']包含了图片文件名
                            logger.info(f"Received image output from node {node_id}: {output['images']}")
                            self.result_queue.put(('output', {node_id: output}))
                            
                elif data['type'] == 'error':
                    # 处理错误信息
                    self.result_queue.put(('error', data['data']['message']))
                    
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
            self.result_queue.put(('error', str(e)))

    def _on_error(self, ws, error):
        logger.error(f"WebSocket error: {error}")
        self.result_queue.put(('error', str(error)))

    def _on_close(self, ws, close_status_code, close_msg):
        logger.info("WebSocket connection closed")

    def _process_execution_result(self, results):
        """
        处理执行结果，获取生成的图片
        ComfyUI的图片输出流程:
        1. WebSocket消息会告知图片的文件名
        2. 图片实际保存在 ComfyUI 的输出目录中
        3. 需要从输出目录读取对应的图片文件
        """
        try:
            processed_result = {
                "images": [],
                "metadata": {}
            }
            
            import folder_paths  # ComfyUI的路径处理模块
            output_dir = folder_paths.get_output_directory()
            
            # 处理每个节点的输出
            for node_id, output in results.items():
                if "images" in output:
                    # ComfyUI的图片输出是一个文件名列表
                    for image_name in output["images"]:
                        image_path = os.path.join(output_dir, image_name)
                        
                        if os.path.exists(image_path):
                            try:
                                # 读取图片文件
                                with open(image_path, "rb") as img_file:
                                    img_data = base64.b64encode(img_file.read()).decode()
                                    
                                processed_result["images"].append({
                                    "data": img_data,
                                    "name": image_name,
                                    "node_id": node_id,
                                    "path": image_path
                                })
                                logger.info(f"Processed image: {image_name} from node {node_id}")
                            except Exception as e:
                                logger.error(f"Error processing image {image_name}: {e}")
                        else:
                            logger.warning(f"Image file not found: {image_path}")
                
                # 保存其他元数据
                processed_result["metadata"][node_id] = {
                    k: v for k, v in output.items() 
                    if k != "images"
                }
            
            if not processed_result["images"]:
                logger.warning("No images found in execution result")
                
            return processed_result
            
        except Exception as e:
            logger.error(f"Error processing execution result: {e}")
            raise
            
    def _get_image_path(self, filename):
        """获取图片的完整��径"""
        try:
            import folder_paths
            output_dir = folder_paths.get_output_directory()
            return os.path.join(output_dir, filename)
        except Exception as e:
            logger.error(f"Error getting image path: {e}")
            return None
            
    def _record_history(self, task, status, result):
        """
        记录任务执行历史
        
        Args:
            task: 任务信息
            status: 执行状态 (completed/failed)
            result: 执行结果或错误信息
        """
        history_item = {
            "task_id": task["id"],
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "result": result
        }
        
        # 添加到历史记录
        self.task_history.append(history_item)
        
        # 限制历史记录数量
        if len(self.task_history) > self.max_history:
            self.task_history = self.task_history[-self.max_history:]
            
        # 保存到文件
        self._save_history()
        
    def _save_history(self):
        """
        保存历史记录到文件
        """
        try:
            history_path = os.path.join(self.base_path, 'task_history.json')
            with open(history_path, 'w') as f:
                json.dump(self.task_history, f)
        except Exception as e:
            logger.error(f"Error saving history: {e}")

    def _load_history(self):
        """
        从文件加载历史记录
        """
        try:
            history_path = os.path.join(self.base_path, 'task_history.json')
            if os.path.exists(history_path):
                with open(history_path, 'r') as f:
                    self.task_history = json.load(f)
        except Exception as e:
            logger.error(f"Error loading history: {e}")
            self.task_history = []

    def _handle_error(self, error, task_id=None):
        """
        统一的错误处理
        
        Args:
            error: 错误信
            task_id: 关的任务ID
        """
        try:
            error_data = {
                "timestamp": datetime.now().isoformat(),
                "error": str(error),
                "task_id": task_id
            }
            
            # 记录错误
            logger.error(f"Task error: {error_data}")
            
            # 如果有关联的任务，提交失败状态
            if task_id:
                self.fog_client.submit_result({
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(error),
                    "completed_at": datetime.now().isoformat()
                })
            
            # 尝试恢复
            self._try_recover()
            
        except Exception as e:
            logger.error(f"Error in error handler: {e}")

    def _try_recover(self):
        """
        尝试从错误中恢复
        - 重置WebSocket连接
        - 清理当前任务状态
        - 重置队列状态
        """
        try:
            # 重置WebSocket
            if self.ws:
                self.ws.close()
                self.ws = None
            
            # 清理当前任务
            self.current_task = None
            self.current_prompt_id = None
            
            # 清空结果队列
            while not self.result_queue.empty():
                self.result_queue.get_nowait()
                
            logger.info("Recovery completed")
            
        except Exception as e:
            logger.error(f"Error in recovery: {e}")

    def _process_images(self, result):
        """处理结果中的图片文件"""
        try:
            import folder_paths  # ComfyUI的路径处理模块
            
            processed_result = {
                "images": [],
                "node_outputs": result  # 保��原始节点输出信息
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

    def __del__(self):
        """清理资源"""
        try:
            if self.ws:
                self.ws.close()
            if hasattr(self, 'ws_thread') and self.ws_thread:
                self.ws_thread.join(timeout=1)
        except Exception as e:
            logger.error(f"Error cleaning up FogScheduler: {e}")
