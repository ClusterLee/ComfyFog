import requests
import logging


from comfy.cli_args import args
from server import PromptServer

logger = logging.getLogger('ComfyFog')

class ComfyUIClient:
    def __init__(self):
        self.prompt_server = PromptServer.instance
        self.address, self.port = self.get_server_info()
        self.scheme = "https" if self.is_tls_enabled() else "http"
        logger.info(f"ComfyUI server running at: {self.scheme}://{self.address}:{self.port}")
        
    def get_server_info(self):
        """获取服务器地址和端口
        优先级：
        1. 从命令行参数获取
        2. 从 PromptServer 实例获取
        3. 使用默认值
        """
        try:
            # 1. 尝试从命令行参数获取
            addresses = args.listen.split(',')
            address = addresses[0] if addresses else "127.0.0.1"
            port = args.port
            logger.debug(f"Got server info from args: {address}:{port}")
            return address, port
        except Exception as e:
            logger.debug(f"Failed to get server info from args: {e}")        

        try:
            # 2. 尝试从 PromptServer 实例获取
            server = PromptServer.instance
            if hasattr(server, 'address') and hasattr(server, 'port'):
                logger.debug(f"Got server info from PromptServer: {server.address}:{server.port}")
                return server.address, server.port
        except Exception as e:
            logger.debug(f"Failed to get server info from PromptServer: {e}")



        # 3. 使用默认值
        logger.debug("Using default server info")
        return "127.0.0.1", 8188

    def is_tls_enabled(self):
        """检查是否启用了 TLS"""
        return bool(args.tls_keyfile and args.tls_certfile)

    def submit_workflow(self, workflow, client_id=None):
        """提交工作流到 ComfyUI"""
        try:
            url = f"{self.scheme}://{self.address}:{self.port}/prompt"
            
            # 准备请求数据
            payload = {
                "prompt": workflow,
                "client_id": client_id
            }
            
            # 发送 POST 请求
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                prompt_id = data.get("prompt_id")
                number = data.get("number")
                node_errors = data.get("node_errors", [])
                
                if prompt_id:
                    logger.info(f"Workflow submitted successfully. Prompt ID: {prompt_id}, Queue number: {number}")
                    return {
                        "success": True,
                        "prompt_id": prompt_id,
                        "number": number,
                        "node_errors": node_errors
                    }
                else:
                    logger.error("No prompt_id in response")
                    return {"success": False, "error": "No prompt_id in response"}
                    
            else:
                error_data = response.json()
                logger.error(f"Failed to submit workflow: {error_data.get('error', 'Unknown error')}")
                return {
                    "success": False,
                    "error": error_data.get('error', 'Unknown error'),
                    "node_errors": error_data.get('node_errors', [])
                }
                
        except Exception as e:
            logger.error(f"Error submitting workflow: {e}")
            return {"success": False, "error": str(e)}

# 使用示例
def example_usage():
    client = ComfyUIClient()
    
    # 工作流示例
    workflow = {
        "3": {
            "inputs": {
                "seed": 123456789,
                "steps": 20,
                "cfg": 7,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0]
            },
            "class_type": "KSampler"
        },
        # ... 其他节点
    }
    
    # 提交工作流
    result = client.submit_workflow(workflow, client_id="my_client_1")
    
    if result["success"]:
        print(f"Workflow submitted with prompt_id: {result['prompt_id']}")
        print(f"Queue position: {result['number']}")
    else:
        print(f"Error: {result['error']}")
        if result.get('node_errors'):
            print(f"Node errors: {result['node_errors']}")

