import random
from typing import Generator

from pydantic import BaseModel

from core.event import Event, EventDispatcher, EventSystem
from core.log import get_logger
from DBHHelper.events import ActEvent, ActionEvent
from DBHLLM.narrator import (
    GetImageDescriptionsEvent,
    GetImageDescriptionsResponse,
    GetPlotSummariesEvent,
    GetPlotSummariesResponse,
)


class TestEvent(Event):
    """Test event with predefined name"""

    name: str = "test_event"


class TestResponseEvent(Event):
    """Response event for testing callbacks"""

    name: str = "response_event"


class TestDispatcher(EventDispatcher):
    """Test dispatcher with predefined handlers"""

    @EventDispatcher.on(TestEvent)
    def handle_test_event(self, param1: str, param2: int = 0) -> Event:
        """Simple handler that returns a response event"""
        return TestResponseEvent(
            name="response_event", kwargs={"result": f"{param1}_{param2}"}
        )

    @EventDispatcher.on(TestEvent)
    def handle_with_generator(self, param1: str) -> Generator[Event, None, None]:
        """Generator handler that yields multiple events"""
        yield TestResponseEvent(
            name="response_event", kwargs={"result": f"gen1_{param1}"}
        )
        yield TestResponseEvent(
            name="response_event", kwargs={"result": f"gen2_{param1}"}
        )


class TestCallbackDispatcher(EventDispatcher):
    @EventDispatcher.on(TestEvent)
    def handle_test_event(self, param1: str, param2: int = 0) -> Event:
        return TestResponseEvent(
            name="response_event", kwargs={"result": f"{param1}_{param2}"}
        )


class MainFlow(EventDispatcher):
    def main(self):
        yield TestEvent(
            kwargs={"param1": "test", "param2": 42}, callback=TestResponseEvent
        )
        e: TestResponseEvent = yield from EventSystem.wait_for_callback()
        assert e.kwargs["result"] == "test_42"
        print(f"main received: {e}")


def test_event_dispatcher_registration():
    """Test event handler registration in EventDispatcher"""
    dispatcher = TestDispatcher()
    handlers = dispatcher.get_event_handlers()

    assert "test_event" in handlers
    assert len(handlers["test_event"]) == 2  # Two handlers registered


def test_event_system():
    """Test event system processing"""
    dispatcher = TestCallbackDispatcher()
    main_flow = MainFlow()
    event_system = EventSystem(main_flow.main, [dispatcher])
    event_system.run()


class ParentDispatcher(EventDispatcher):
    """Parent dispatcher with event handler"""

    @EventDispatcher.on(TestEvent)
    def handle_test_event(self, param1: str, param2: int = 0) -> Event:
        return TestResponseEvent(
            name="response_event", kwargs={"result": f"{param1}_{param2}"}
        )


class ChildDispatcher(ParentDispatcher):
    """Child dispatcher inheriting from ParentDispatcher"""

    pass


def test_event_inheritance():
    """Test event inheritance in dispatchers"""
    parent_dispatcher = ParentDispatcher()
    child_dispatcher = ChildDispatcher()

    # Check if child dispatcher has inherited handlers
    handlers = child_dispatcher.get_event_handlers()
    assert "test_event" in handlers
    assert len(handlers["test_event"]) == 1  # Inherited from parent dispatcher


def test_flow_event():
    """Test flow event processing"""
    from DBHHelper.flows.flow_01 import Flow

    flow = Flow(None, {})
    handlers = flow.get_event_handlers()
    assert "event_system_close_event" in handlers


class GetFooEvent(Event):
    """GetFoo event with predefined name"""

    name: str = "get_foo_event"


class GetFooResponseEvent(Event):
    """Response event for GetFoo"""

    name: str = "get_foo_response_event"

    class Kwargs(BaseModel):
        foo: str

    kwargs: Kwargs


class GetBarEvent(Event):
    """GetBar event with predefined name"""

    name: str = "get_bar_event"

    class Kwargs(BaseModel):
        bar: str

    kwargs: Kwargs


class GetBarResponseEvent(Event):
    """Response event for GetBar"""

    name: str = "get_bar_response_event"

    class Kwargs(BaseModel):
        bar: str

    kwargs: Kwargs


class AgentA(EventDispatcher):
    """Agent A dispatcher"""

    @EventDispatcher.on(GetFooEvent)
    def handle_get_foo_event(self) -> Event:
        return GetFooResponseEvent(kwargs={"foo": "foo"})

    @EventDispatcher.on(GetBarEvent)
    def handle_get_bar_event(self, bar: str) -> Event:
        return GetBarResponseEvent(kwargs={"bar": bar + "bar"})


class AgentB(EventDispatcher):
    """Agent B dispatcher"""

    def __init__(self):
        self._logger = get_logger()

    @EventDispatcher.on(TestEvent)
    def handle_test_event(self):
        self._logger.info("Agent B received TestEvent")
        yield GetFooEvent(callback=GetFooResponseEvent)
        self._logger.info("Waiting for foo")
        foo: GetFooResponseEvent = yield from EventSystem.wait_for_callback()
        self._logger.info(f"Received foo {foo.kwargs.foo}")
        yield GetBarEvent(kwargs={"bar": "bar"}, callback=GetBarResponseEvent)
        self._logger.info("Waiting for bar")
        bar: GetBarResponseEvent = yield from EventSystem.wait_for_callback()
        self._logger.info(f"Received bar {bar.kwargs.bar}")
        self.foo = foo.kwargs.foo
        self.bar = bar.kwargs.bar


def test_agent_interaction():
    """Test interaction between agents"""
    agent_a = AgentA()
    agent_b = AgentB()

    event_system = EventSystem(None, [agent_a, agent_b])
    event_system.one_event(TestEvent(), "TestEvent")
    assert agent_b.foo == "foo"
    assert agent_b.bar == "barbar"


class Flow(EventDispatcher):
    def __init__(self):
        self._logger = get_logger()

    def foo(self):
        self._logger.info("Flow foo")
        yield GetFooEvent(callback=GetFooResponseEvent)
        self._logger.info("Waiting for foo")
        foo: GetFooResponseEvent = yield from EventSystem.wait_for_callback()
        assert foo.kwargs.foo == "foo"
        self._logger.info(f"foo: {foo.kwargs.foo}")
        return foo.kwargs.foo

    def call_agent_b(self):
        yield TestEvent()

    def run(self):
        yield from self.foo()
        yield from self.call_agent_b()
        yield from self.foo()


def test_flow():
    """Test flow execution"""
    flow = Flow()
    agent_a = AgentA()
    agent_b = AgentB()
    event_system = EventSystem(flow.run, [agent_a, agent_b])
    event_system.run()


class DummyNarrator(EventDispatcher):
    """Dummy narrator for testing"""

    def __init__(self):
        self._logger = get_logger()

    @EventDispatcher.on(GetImageDescriptionsEvent)
    def get_image_descriptions(
        self, indexes: tuple[int, ...]
    ) -> GetImageDescriptionsResponse:
        """Get the image descriptions from the previous summaries"""
        image_descriptions = "Dummy image descriptions"
        return GetImageDescriptionsResponse(
            kwargs={"image_descriptions": image_descriptions}
        )

    @EventDispatcher.on(GetPlotSummariesEvent)
    def get_plot_summaries(self, indexes: tuple[int, ...]) -> GetPlotSummariesResponse:
        """Get the plot summaries from the previous summaries"""
        plot_summaries = "Dummy plot summaries"
        return GetPlotSummariesResponse(kwargs={"plot_summaries": plot_summaries})


class DummyPlayer(EventDispatcher):
    """Dummy player for testing"""

    def __init__(self):
        self._logger = get_logger()

    @EventDispatcher.on(ActEvent)
    def choose(self, key: str, context: str, choices: dict, info: dict) -> ActionEvent:
        self._logger.info(f"Choosing from {choices}")
        yield GetImageDescriptionsEvent(
            kwargs={"indexes": (0, 1, 2, 3, 4)}, callback=GetImageDescriptionsResponse
        )
        image_description: GetImageDescriptionsResponse = yield from EventSystem.wait_for_callback()
        assert image_description.kwargs.image_descriptions == "Dummy image descriptions"
        yield GetPlotSummariesEvent(
            kwargs={"indexes": (0, 1, 2, 3)}, callback=GetPlotSummariesResponse
        )
        plot_summaries: GetPlotSummariesResponse = yield from EventSystem.wait_for_callback()
        assert plot_summaries.kwargs.plot_summaries == "Dummy plot summaries"
        choice = random.choice(list(choices.keys()))
        choice_text = choices[choice]
        return ActionEvent(kwargs={"choice_key": choice, "choice_text": choice_text})


class DummyFlow(EventDispatcher):
    def __init__(self):
        self._logger = get_logger()

    def act(self):
        yield ActEvent(
            kwargs={
                "key": "test_key",
                "context": "test_context",
                "choices": {"choice1": "Choice 1", "choice2": "Choice 2"},
                "info": {"status": {}, "choices": {"choice1": "Choice 1", "choice2": "Choice 2"}, "context": "test_context"},
            },
            callback=ActionEvent,
        )

    def run(self):
        yield from self.act()
        action = yield from EventSystem.wait_for_callback()
        self.action = action


def test_action_event():
    """Test action event processing"""
    narrator = DummyNarrator()
    player = DummyPlayer()
    flow = DummyFlow()
    event_system = EventSystem(flow.run, [narrator, player])
    event_system.run()
    assert flow.action.kwargs.choice_key in ["choice1", "choice2"]
    assert flow.action.kwargs.choice_text in ["Choice 1", "Choice 2"]
