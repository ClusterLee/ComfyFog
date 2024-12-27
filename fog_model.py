import os
import logging
import folder_paths

logger = logging.getLogger('ComfyFog')


class FogModel:
    def __init__(self):
  
        # 添加ComfyFog 额外模型目录，通常为远程目录，本地comfyui模型目录优先

        try:
            fog_model_dir = os.path.join(os.path.dirname(__file__), "models")
            fog_mode_checkpoints = os.path.join(fog_model_dir, "checkpoints")
            folder_paths.add_model_folder_path("checkpoints", fog_mode_checkpoints)
            
            if not os.path.exists(fog_mode_checkpoints):
                os.makedirs(fog_mode_checkpoints)

        except Exception as e:
            logger.error(f"Failed to init FogModel: {e}")        

        return
        
    def get_folder_paths_info(self):

        try:
            logger.debug( f"【folder_paths info】\n {folder_paths.folder_names_and_paths}")
        except Exception as e:
            logger.error(f"Failed to get get_folder_paths: {e}")        

        return 