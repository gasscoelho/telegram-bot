from enum import Enum


# What the user selected
class Kind(Enum):
    TRUCK = "truck"
    BUILD = "build"
    RESEARCH = "research"
    TRAIN = "train"
    MINISTRY = "ministry"
    CUSTOM = "custom"
    LIST = "list"
    CANCEL = "cancel"
