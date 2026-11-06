import inspect
import os
import sys
from typing import Any, Callable, Dict, Generator, List, Union

from pydantic import BaseModel, Field
from rich.pretty import pretty_repr

from core.log import get_logger


class Event(BaseModel):
    name: str
    kwargs: Dict[str, Any] = Field(default_factory=dict)
    callback: Any = None


class EventSystemStartEvent(Event):
    name: str = "event_system_start_event"


class EventSystemCallbackDropEvent(Event):
    name: str = "event_system_callback_drop_event"


class EventSystemCloseEvent(Event):
    name: str = "event_system_close_event"


def unpack_kwargs(kwargs):
    if isinstance(kwargs, dict):
        return kwargs
    elif isinstance(kwargs, BaseModel):
        return kwargs.model_dump()
    else:
        raise TypeError("kwargs must be a dict or a Pydantic model instance")


def filter_kwargs(func, kwargs):
    """Filters kwargs based on func's signature, retaining only the parameters that func accepts.
    If func accepts **kwargs, no filtering is performed.
    """
    sig = inspect.signature(func)
    # If func has a **kwargs parameter, return all kwargs without filtering
    if any(param.kind == param.VAR_KEYWORD for param in sig.parameters.values()):
        return kwargs
    # Otherwise, retain only the parameters defined in the function's signature
    valid_keys = set(sig.parameters.keys())
    return {k: v for k, v in kwargs.items() if k in valid_keys}


EVENTSYSTEM_MAIN = "EVENTSYSTEM_MAIN"


class EventDispatcher:
    _event_handlers: Dict[str, List[Callable]] = {}

    @classmethod
    def on(cls, event_type: Union[type[Event], List[type[Event]]]):
        """Decorator to mark a method as a handler for a specific event type"""

        def decorator(func: Callable):
            # Store the event type in the function attribute
            func._event_type = (
                event_type if isinstance(event_type, list) else [event_type]
            )
            return func

        return decorator

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Each subclass gets its own _event_handlers dictionary
        cls._event_handlers = {}
        # Iterate over all attributes of the subclass to collect methods marked as event handlers
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if callable(attr) and hasattr(attr, "_event_type"):
                event_type: List[type[Event]] = getattr(attr, "_event_type")
                for eve in event_type:
                    # Use the event type's class name as the key
                    key = eve.model_fields["name"].default
                    cls._event_handlers.setdefault(key, []).append((id(eve), attr))

    def dispatch(self, event: Event) -> Generator[Event, None, None]:
        """Triggers the specified event type and executes all bound handler functions"""
        handlers = self._event_handlers.get(event.name, [])
        for _, handler in handlers:
            filtered_kwargs = filter_kwargs(handler, unpack_kwargs(event.kwargs))
            ret = handler(self, **filtered_kwargs)
            if inspect.isgenerator(ret):
                yield ret
            elif isinstance(ret, Event):
                yield ret

    def get_event_handlers(self):
        return self._event_handlers


def get_full_generator_stack(gen):
    """
    Given an outer generator, recursively retrieve the stack frames for it and any delegated
    subgenerators (using yield from). Returns a list of lists. Each inner list contains strings
    describing the outer frames for that generator level.
    """
    stacks = []
    current_gen = gen
    while current_gen is not None:
        frame = current_gen.gi_frame
        if frame is None:
            stacks.append(["No frame available (generator may be exhausted)"])
        else:
            outer_frames = inspect.getouterframes(frame)
            stack_info = []
            for frame_detail in outer_frames:
                # Unpack the frame details.
                frame_obj, filename, line_no, function, code_context, index = (
                    frame_detail
                )
                code_line = code_context[0].strip() if code_context else ""
                stack_info.append(
                    f"File: {filename}, Function: {function}, Line: {line_no}, Code: {code_line}"
                )
            stacks.append(stack_info)
        # Move to the delegated generator, if any.
        current_gen = getattr(current_gen, "gi_yieldfrom", None)
    return stacks


class EventSystem:
    _event_triggers: dict[str, List[EventDispatcher]]

    def __init__(
        self, main: Generator[Event, Event, None], triggers: List[EventDispatcher]
    ):
        assert inspect.isgeneratorfunction(main) or main is None, (
            "Main generator must be a generator function"
        )
        self.main = main() if main else None
        self.triggers = triggers
        self._logger = get_logger()
        self._debug_level = int(os.getenv("flags.debug", "1"))
        self.setup()

    def setup(self):
        self._trigger_g = []
        self._callback_g = {}
        self._events = []
        self._event_triggers = {}
        events = {}
        for trigger in self.triggers:
            eh = trigger.get_event_handlers()
            if not eh:
                self._logger.warning(
                    f"Trigger {trigger.__class__.__name__} has no event handlers",
                )
                continue
            for event_name in eh:
                if event_name in events:
                    assert events[event_name][0] == eh[event_name][0][0], (
                        f"Same event name {event_name} with different event classes"
                    )
                else:
                    events[event_name] = eh[event_name][0]
                self._event_triggers.setdefault(event_name, []).append(trigger)
                self._logger.debug(
                    f"Added trigger {trigger.__class__.__name__} "
                    f"for event {event_name} "
                    f"handlers: {eh[event_name]}"
                )

    def add_event(self, event: Event, cls: str, g: Generator = None):
        if self._debug_level >= 1:
            self._logger.debug(
                f"Received event from trigger {cls}: {pretty_repr(event)}"
            )
        self._events.append(event)
        if event.callback and issubclass(event.callback, Event):
            if self._debug_level >= 2:
                self._logger.debug(
                    f"Nexting generator {g} from {cls}, {pretty_repr(get_full_generator_stack(g))}"
                )
            # For stoping at next yield
            next(g)
            self._callback_g.setdefault(event.callback, []).append((cls, g))
            if self._debug_level >= 2:
                self._logger.debug(
                    f"Added callback {event.callback} for event: "
                    f"{pretty_repr(event)}, {pretty_repr(get_full_generator_stack(g))}"
                )
            return True
        return False

    @staticmethod
    def wait_for_callback():
        res = yield
        yield EventSystemCallbackDropEvent()
        return res

    def process_callback(self, event: Event):
        if event.__class__ not in self._callback_g:
            return
        for _cls, _g in self._callback_g[event.__class__][::-1]:
            try:
                if self._debug_level >= 2:
                    self._logger.debug(
                        f"Resuming {_cls} callback {_g} for event: "
                        f"{pretty_repr(event)}, {pretty_repr(get_full_generator_stack(_g))}"
                    )
                ret = _g.send(event)
                if self._debug_level >= 2:
                    self._logger.debug(
                        f"Callback {_cls} {_g} yielded: "
                        f"{pretty_repr(ret)}, {pretty_repr(get_full_generator_stack(_g))}"
                    )
                if isinstance(ret, EventSystemCallbackDropEvent):
                    if _cls == EVENTSYSTEM_MAIN:
                        continue
                    if self._debug_level >= 2:
                        self._logger.debug(
                            f"Adding back trigger {_cls} {_g} for event: {pretty_repr(ret)}"
                        )
                    self._trigger_g.append((_cls, _g))
                elif isinstance(ret, Event):
                    has_callback = self.add_event(ret, _cls, _g)
                    if has_callback:
                        continue
                    if _cls == EVENTSYSTEM_MAIN:
                        continue
                    if self._debug_level >= 2:
                        self._logger.debug(
                            f"Adding back trigger {_cls} {_g} for event: {pretty_repr(ret)}"
                        )
                    self._trigger_g.append((_cls, _g))
            except StopIteration:
                if self._debug_level >= 2:
                    self._logger.debug(f"Callback {_cls} {_g} finished")
        self._callback_g.pop(event.__class__)

    def handle_event(self, event: Event):
        if self._debug_level >= 1:
            self._logger.debug(f"Processing event: {pretty_repr(event)}")
        if event.name in self._event_triggers:
            for trigger in self._event_triggers[event.name]:
                if self._debug_level >= 2:
                    self._logger.debug(
                        f"Dispatching event {pretty_repr(event)} to trigger {trigger.__class__.__name__}"
                    )
                self._trigger_g.append(
                    (trigger.__class__.__name__, trigger.dispatch(event))
                )
        self.process_callback(event)
        _new_trigger_g = []
        if self._debug_level >= 2:
            self._logger.debug(f"Trigger generators: {pretty_repr(self._trigger_g)}")
        for _cls, _g in self._trigger_g:
            try:
                if self._debug_level >= 2:
                    self._logger.debug(
                        f"Nexting generator {_g} from {_cls}, {pretty_repr(get_full_generator_stack(_g))}"
                    )
                ret = next(_g)
                if self._debug_level >= 2:
                    self._logger.debug(
                        f"Generator from {_cls} yielded: "
                        f"{pretty_repr(ret)}, {pretty_repr(get_full_generator_stack(_g))}"
                    )
                if inspect.isgenerator(ret):
                    # avoid empty _events
                    _event = next(ret)
                    if self._debug_level >= 2:
                        self._logger.debug(
                            f"Generator from {_cls} yielded generator: "
                            f"{pretty_repr(_event)}, {pretty_repr(get_full_generator_stack(ret))}"
                        )
                    has_callback = self.add_event(_event, _cls, ret)
                    if not has_callback:
                        _new_trigger_g.append((_cls, ret))
                        if self._debug_level >= 2:
                            self._logger.debug(
                                f"Adding new trigger {_cls} {ret} for event: {pretty_repr(_event)}"
                            )
                    _new_trigger_g.append((_cls, _g))
                    if self._debug_level >= 2:
                        self._logger.debug(
                            f"Adding new trigger {_cls} {_g} for generator: {pretty_repr(ret)}"
                        )
                else:
                    if isinstance(ret, EventSystemCallbackDropEvent):
                        continue
                    has_callback = self.add_event(ret, _cls, _g)
                    if not has_callback:
                        _new_trigger_g.append((_cls, _g))
                        if self._debug_level >= 2:
                            self._logger.debug(
                                f"Adding new trigger {_cls} {_g} for event: {pretty_repr(ret)}"
                            )
            except StopIteration as e:
                if self._debug_level >= 2:
                    self._logger.debug(
                        f"Generator {_g} from {_cls} finished with {pretty_repr(e.value)}, removing from trigger list"
                    )
                if isinstance(e.value, Event):
                    has_callback = self.add_event(e.value, _cls, _g)
                    assert not has_callback
            except Exception as e:
                for _, g in self._trigger_g:
                    try:
                        g.close()
                    except Exception:
                        pass
                raise e
        self._trigger_g = _new_trigger_g
        self.validate()

    def validate(self):
        # Validation
        gs = set()
        for cls, g in self._trigger_g:
            assert g not in gs
            gs.add(g)
        for callbacks in self._callback_g.values():
            for _, g in callbacks:
                assert g not in gs
                gs.add(g)
        return gs

    def loop_events(self):
        while self._events:
            if self._debug_level >= 2:
                self._logger.debug(f"Events queue: {pretty_repr(self._events)}")
            event = self._events.pop(0)
            self.handle_event(event)

    def run(self):
        if not self.main:
            self._logger.warning(
                "Main generator is None, skipping run",
            )
            return
        self._trigger_g = []
        self._callback_g = {}
        self.add_event(EventSystemStartEvent(), "EventSystem")
        try:
            self.loop_events()
            while True:
                try:
                    if self._debug_level >= 2:
                        self._logger.debug(
                            f"Main generator next, {pretty_repr(get_full_generator_stack(self.main))}"
                        )
                    ret = next(self.main)
                    if self._debug_level >= 2:
                        self._logger.debug(
                            f"Main generator yielded: "
                            f"{pretty_repr(ret)}, {pretty_repr(get_full_generator_stack(self.main))}"
                        )
                    if not isinstance(ret, EventSystemCallbackDropEvent):
                        self.add_event(ret, EVENTSYSTEM_MAIN, self.main)
                except StopIteration:
                    if self._debug_level >= 2:
                        self._logger.debug("Main generator finished")
                    break
                self.loop_events()
        except Exception as e:
            self.close_generators()
            raise e

    def close_generators(self):
        for _, g in self._trigger_g:
            try:
                g.close()
            except Exception:
                pass
        for callbacks in self._callback_g.values():
            for _, g in callbacks:
                try:
                    g.close()
                except Exception:
                    pass
        try:
            self.main.close()
        except Exception:
            pass

    def clear(self):
        self.close_generators()
        self._trigger_g = []
        self._callback_g = {}
        self._events = []
        self.main = None

    def one_event(self, event: Event, cls: str):
        """Process a single event"""
        self.clear()
        self.add_event(event, cls)
        self.loop_events()

    def close(self):
        self.one_event(EventSystemCloseEvent(), "EventSystem")
