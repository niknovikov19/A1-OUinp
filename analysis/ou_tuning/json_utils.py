from dataclasses import is_dataclass
import json

import numpy as np


class CustomEncoder(json.JSONEncoder):
    """JSON encoder that treats ndarrays and dataclasses."""    
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()        
        if isinstance(obj, np.integer):
            return int(obj)      
        if isinstance(obj, np.floating):
            return float(obj) 
        if is_dataclass(obj):
            return obj.__dict__
        return super().default(obj)
