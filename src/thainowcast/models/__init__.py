from .base import NowcastModel
from .benchmarks import AR, RandomWalk
from .bridge import Bridge
from .dfm import DFM
from .midas import MIDAS
from .ml import ElasticNetNowcast, LightGBMNowcast

MODELS = {
    "rw": RandomWalk,
    "ar": AR,
    "bridge": Bridge,
    "midas": MIDAS,
    "dfm": DFM,
    "enet": ElasticNetNowcast,
    "lgbm": LightGBMNowcast,
}

__all__ = ["AR", "DFM", "MIDAS", "MODELS", "Bridge", "ElasticNetNowcast", "LightGBMNowcast", "NowcastModel", "RandomWalk"]
