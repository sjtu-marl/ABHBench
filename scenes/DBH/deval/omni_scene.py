import argparse
import logging
import os

from ABHBench.deval.helper import DEvalHelper
from core.scenario import Scenario
from DBHHelper.utils import get_flow_info, read_flow_cfg
from DBHLLM.omni_player import OmniPlayer


class Scen(Scenario):
    def __init__(self, datasets_dir):
        # Get Flow info at runtime
        Flow, CHAPTER_STR = get_flow_info()
        super().__init__(
            "DBH DEval",
            f"flow_{CHAPTER_STR}",
            levels=(
                logging.DEBUG
                if os.getenv("flags.console_debug", "false").lower() == "true"
                else logging.INFO,
                logging.INFO,
                logging.DEBUG,
            ),
            tags=["DBH", "DEval", "OMNI"],
        )
        self.datasets_dir = datasets_dir

    def setup(self):
        # Get Flow info at runtime
        Flow, CHAPTER_STR = get_flow_info()
        flow_cfg = read_flow_cfg(f"flow_{CHAPTER_STR}.yaml")
        dbhh = DEvalHelper(flow_cfg, self.datasets_dir)
        flow = Flow(dbhh, flow_cfg, auto=-1)
        flow.setup()
        dbhh.setup()

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

    # Get Flow info at runtime
    Flow, CHAPTER_STR = get_flow_info()

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run Offline Evaluation for DBH scene")
    parser.add_argument(
        "--datasets-dir",
        type=str,
        default=f"datasets/dataset_flow_{CHAPTER_STR}",
        help="Directory containing datasets for evaluation",
    )
    args = parser.parse_args()

    sys.exit(Scen(datasets_dir=args.datasets_dir).run())
