import requests
import logging
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from typing import Optional, Dict, Any
from datetime import datetime
from urllib.parse import urlparse, urljoin

logger = logging.getLogger('ComfyFog')

class FogClient:
    """
    任务中心客户端
    负责与远程任务中心通信，获取任务和提交结果
    """
    def __init__(self, task_center_url: str):
        self.task_center_url = task_center_url
        self.session = self._create_session()
        self.timeout = 10  # 添加默认超时时间
        
    def _create_session(self):
        """
        创建HTTP会话
        配置重试策略和超时设置
        """
        session = requests.Session()
        retry = Retry(
            total=3,  # 最大重试次数
            backoff_factor=0.5,  # 重试间隔
            status_forcelist=[500, 502, 503, 504]  # 需要重试的HTTP状态码
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
        logger.info(f"Fetching task from: {self.task_center_url}/task")
        try:
            response = self.session.get(
                f"{self.task_center_url}/task",
                headers={'User-Agent': 'ComfyFog/1.0'},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                task = response.json()
                logger.info(f"Received task: {task.get('id')}")
                return task
            elif response.status_code == 404:
                logger.debug("No tasks available")
            else:
                logger.warning(f"Failed to fetch task: {response.status_code}")
            return None
                
        except Exception as e:
            logger.error(f"Error fetching task: {str(e)}")
            return None
            
    def submit_result(self, result: Dict[str, Any]) -> bool:
        """
        提交任务结果到任务中心
        
        预期API: POST /result
        
        Args:
            result (Dict[str, Any]): 结果数据，格式如下:
            {
                "task_id": str,          # 任务ID
                "status": str,           # 状态: "completed" 或 "failed"
                "completed_at": str,     # 完成时间，ISO格式
                "images": [              # 生成的图片列表
                    {
                        "data": str,     # base64编码的图片数据
                        "filename": str,  # 图片文件名
                        "node_id": str,  # 生成该图片的节点ID
                        "type": str      # 图片类型，如 "output"
                    }
                ],
                "node_outputs": {        # ComfyUI节点输出数据
                    "node_id": {         # 节点ID
                        "images": [      # 该节点生成的图片信息
                            {
                                "filename": str,
                                "subfolder": str,
                                "type": str
                            }
                        ],
                        # ... 其他节点特定输出
                    }
                },
                "error": str            # 可选，失败时的错误信息
            }
            
        Returns:
            bool: 提交是否成功
            
        Raises:
            ValueError: 结果数据格式无效
        """
        # 验证必要字段
        required_fields = ['task_id', 'status']
        if not all(field in result for field in required_fields):
            raise ValueError(f"Missing required fields: {required_fields}")
            
        # 验证状态值
        if result['status'] not in ['completed', 'failed']:
            raise ValueError("Invalid status value")
            
        # 确保completed_at存在且格式正确
        if 'completed_at' not in result:
            result['completed_at'] = datetime.now().isoformat()
            
        try:
            response = self.session.post(
                urljoin(self.task_center_url, 'result'),
                json=result,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                logger.info(f"Result submitted for task: {result['task_id']}")
                return True
            else:
                logger.warning(
                    f"Failed to submit result: {response.status_code}, "
                    f"task_id: {result['task_id']}, "
                    f"status: {result['status']}"
                )
                return False
                
        except Exception as e:
            logger.error(f"Error submitting result: {str(e)}")
            return False
        
    def test_connection(self) -> bool:
        """
        测试与任务中心的连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            response = self.session.get(
                f"{self.task_center_url}/health",
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
