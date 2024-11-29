import logging
import requests
import traceback  
import urllib.parse
import os

from datetime import datetime
from urllib3.util import Retry
from typing import Optional, Dict, Any
from requests.adapters import HTTPAdapter


logger = logging.getLogger('ComfyFog')

class FogClient:
    """
    任务中心客户端
    负责与远程任务中心通信，获取任务和提交结果
    """
    def __init__(self, task_center_url: str):
        self.task_center_url = task_center_url
        self.session = self._create_session()
        self.timeout = 30  # 添加默认超时时间
        
    def _create_session(self):
        """
        创建HTTP会话
        配置重试策略和超时设置
        """
        session = requests.Session()
        retry = Retry(
            total=2,  # 最大重试次数
            backoff_factor=5,  # 每次重试间隔5秒
            status_forcelist=[],  # 清空状态码列表，不根据状态码重试
            allowed_methods=None,  # 允许所有 HTTP 方法重试
            raise_on_status=False,  # 不因状态码抛出异常
            connect=5,  # 连接超时重试
            read=30     # 读取超时重试
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session
        
    def fetch_task(self):
        """
        从任务中心获取任务
        预期API: GET /task
        返回格式: {
            "id": "task_id",
            "workflow": {...},  # ComfyUI工作流数据
            "created_at": "2024-01-01T00:00:00Z"
        }
        """
        logger.debug(f"Fetching task from: {self.task_center_url}/get")
        try:
            response = self.session.get(
                f"{self.task_center_url}/get",
                headers={'User-Agent': 'ComfyFog/1.0'},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                try:
                    task = response.json()
                    if not task.get('task_id'):
                        raise Exception(f"Invalid task format - missing 'task_id' field. Response: {task}")

                    if not task.get('workflow'):
                        raise Exception(f"Invalid task format - missing 'workflow' field. Response: {task}")

                    return {
                        "success": True,
                        "task_id": task.get('task_id'),
                        "workflow": task.get('workflow'),
                        "create_at": task.get('create_at')
                    }
                
                except ValueError as e:
                    raise Exception(f"Invalid JSON response: {e}. Raw response: {response.text}")

            else:
                raise Exception(f"Failed to fetch task: {response.status_code}, Response: {response.text}")
            
                
        except Exception as e:
            error_msg = f"Error fetching task, {str(e)}"
            return {
                "success": False,
                "error": error_msg
            }
    
    """
    
    Inputs: images:{'9': {'url': ['http://127.0.0.1:8188/view?filename=ComfyUI_01209_.png&subfolder=&type=output'], 'file': ['/data/home/clusterli/ComfyUI/output/ComfyUI_01209_.png']}}
    Resp: 
    """
    def upload_images(self, meta:Dict[str, Any], images: Dict[str, Any], resp: Dict[str, Any]) -> bool:
       
        # 初始化返回
        ret = True
        for node, details in images.items():
            files = details.get('file', [])
            resp[node] = []
            for index,file in enumerate(files):
                resp[node].append({"success": False, "file":file, "error": ""})
        


        task_post_url = "{}/upload?{}".format(self.task_center_url, urllib.parse.urlencode(meta))
        # 遍历 images 字典
        for node, details in images.items():

            files = details.get('file', [])
                  
            for index,file in enumerate(files):
                post_url = "{}&node={}&index={}".format(task_post_url, node, index)
                logger.debug(f"submit post url {post_url}")

                try:
                    # 上传本地生成文件
                    with open(file, 'rb') as f:
                        file_data = f.read()  # 读取文件内容
                        response = self.session.post(
                            f"{post_url}",
                            headers={
                                'User-Agent': 'ComfyFog/1.0',
                                'Content-Type': 'application/octet-stream'  # 设置内容类型
                            },
                            data=file_data,  # 直接发送文件内容
                            timeout=self.timeout
                        )

                        # 检查响应状态
                        if response.status_code == 200:
                            # 获取响应内容
                            response_data = response.json()  # 假设返回的是 JSON 格式
                            logger.debug(f"File {file} uploaded successfully. Response: {response_data}")
                            
                            # 在 resp 中记录上传成功的状态
                            resp[node][index] = {"success": True, "file": file}
                            
                            # 删除本地文件
                            try:
                                os.remove(file)  # 删除本地文件
                                logger.debug(f"Local file {file} deleted successfully.")
                            except OSError as e:
                                logger.error(f"Error deleting file {file}: {e}")
                        else:
                            raise Exception(f"Failed to upload {file}. Status code: {response.status_code}")
                            

                except Exception as e:
                    ret = False
                    err_msg = (f"Error upload image: {str(e)}")
                    resp[node][index] = {"success":False, "file":file, "error": err_msg }

        return ret



