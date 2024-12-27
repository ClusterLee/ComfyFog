import logging
import folder_paths

logger = logging.getLogger('ComfyFog')


class FogModel:
    def __init__(self):

        return
        
    def get_folder_paths_info(self):

        try:
            logger.debug( f"-------------folder_paths info-------------\n: {folder_paths.folder_names_and_paths}")
        except Exception as e:
            logger.error(f"Failed to get get_folder_paths: {e}")        

        return 