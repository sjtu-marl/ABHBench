import logging
import os

from core.scenario import Scenario
from DBHHelper.helper import DBHHelper
from DBHHelper.utils import get_flow_info, read_flow_cfg
from DBHLLM.omni_player import OmniPlayer


class Scen(Scenario):
    def __init__(self):
        # Get Flow info at runtime
        Flow, CHAPTER_STR = get_flow_info()
        super().__init__(
            "DBH",
            f"flow_{CHAPTER_STR}",
            levels=(
                logging.DEBUG
                if os.getenv("flags.console_debug", "false").lower() == "true"
                else logging.INFO,
                logging.INFO,
                logging.DEBUG,
            ),
            tags=["DBH", "OMNI"],
        )

    def setup(self):
        # Get Flow info at runtime
        Flow, CHAPTER_STR = get_flow_info()
        flow_cfg = read_flow_cfg(f"flow_{CHAPTER_STR}.yaml")
        dbhh = DBHHelper(flow_cfg)
        flow = Flow(dbhh, flow_cfg, auto=-1)
        flow.setup()
        dbhh.setup(
            obs_interval=int(os.getenv("agent.obs_interval", 10)),
            obs_move_interval=int(os.getenv("agent.obs_move_interval", 30)),
        )

        # Create the OmniPlayer instance that handles both image processing and decision making
        omni_player = OmniPlayer(
            chapter_summary=flow_cfg["CHAPTER_SUMMARY"],
            protagonist_summary=flow_cfg["PROTAGONIST_SUMMARY"],
            key_characters=flow_cfg["KEY_CHARACTERS"],
            important_choices=flow_cfg.get("IMPORTANT_CHOICES", []),
        )

        self.main_g = flow.run
        self.triggers = [dbhh, flow, omni_player]


if __name__ == "__main__":
    import sys

    sys.exit(Scen().run())
