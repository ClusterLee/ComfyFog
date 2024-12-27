import os
import logging
import folder_paths

logger = logging.getLogger('ComfyFog')


class FogModel:
    def __init__(self):
         
        # 添加ComfyFog 额外模型目录，通常为远程目录，本地comfyui模型目录优先
        
        try:
            self._add_model_folder_path("checkpoints")
            self._add_model_folder_path("controlnet")
            self._add_model_folder_path("loras")

        except Exception as e:
            logger.error(f"Failed to init FogModel: {e}")        

        return
    
    def _add_model_folder_path(self, folder_name):
        
        fog_model_base_dir = os.path.join(os.path.dirname(__file__), "models")
        fog_mode_dir = os.path.join(fog_model_base_dir, folder_name)
        folder_paths.add_model_folder_path(folder_name, fog_mode_dir)
        if not os.path.exists(fog_mode_dir):
            os.makedirs(fog_mode_dir)

        return 

    def get_folder_paths_info(self):

        try:
            logger.debug( f"【folder_paths info】\n {folder_paths.folder_names_and_paths}")
        except Exception as e:
            logger.error(f"Failed to get get_folder_paths: {e}")        

        return 