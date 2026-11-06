from PIL import Image
from pydantic import BaseModel

from core.event import Event, EventDispatcher


class ObsEvent(Event):
    name: str = "obs"

    class Kwargs(BaseModel):
        obs: Image.Image

        model_config = {"arbitrary_types_allowed": True}

    kwargs: Kwargs


class ObsWithContextEvent(Event):
    name: str = "obs_with_context"

    class Kwargs(BaseModel):
        obs: Image.Image
        context: str

        model_config = {"arbitrary_types_allowed": True}

    kwargs: Kwargs


class ObsWithContextAndChoicesEvent(Event):
    name: str = "obs_with_context_and_choices"

    class Kwargs(BaseModel):
        obs: Image.Image
        context: str
        choices: dict

        model_config = {"arbitrary_types_allowed": True}

    kwargs: Kwargs


class ObsWithActEvent(Event):
    name: str = "obs_with_act"

    class Kwargs(BaseModel):
        obs: Image.Image
        act: str

        model_config = {"arbitrary_types_allowed": True}

    kwargs: Kwargs


class ActEvent(Event):
    name: str = "act"

    class Kwargs(BaseModel):
        key: str
        context: str
        choices: dict
        info: dict

    kwargs: Kwargs


class ActionEvent(Event):
    name: str = "action"

    class Kwargs(BaseModel):
        choice_key: str
        choice_text: str

    kwargs: Kwargs
