import argparse
import logging
import os
import sys

import yaml

from core.scenario import Scenario
from DBHHelper.helper import DBHHelper
from DBHHelper.utils import get_flow_info, read_flow_cfg
from DBHLLM.narrator import DummyLLMNarrator as LLMNarrator
from DBHLLM.player import DummyLLMPlayer as LLMPlayer


class Scen(Scenario):
    def __init__(self, predefine_yaml=None):
        # Get Flow info at runtime
        Flow, CHAPTER_STR = get_flow_info()
        super().__init__(
            "DBH_Extra",
            f"flow_{CHAPTER_STR}",
            levels=(
                logging.DEBUG
                if os.getenv("flags.console_debug", "false").lower() == "true"
                else logging.INFO,
                logging.INFO,
                logging.DEBUG,
            ),
            tags=["DBH", "Dummy"],
        )
        self.predefine_yaml = predefine_yaml

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
        llm_nar = LLMNarrator()
        llm_ply = LLMPlayer()

        # Set predefined choices if a YAML file was provided
        if hasattr(self, "predefine_yaml") and self.predefine_yaml is not None:
            try:
                if not os.path.exists(self.predefine_yaml):
                    self._logger.error(
                        f"Predefined YAML file does not exist: {self.predefine_yaml}"
                    )
                else:
                    with open(self.predefine_yaml, "r") as f:
                        try:
                            predefined_choices = yaml.safe_load(f)
                            if predefined_choices is not None:
                                llm_ply.PREDEFINED = predefined_choices
                                self._logger.info(
                                    f"Loaded predefined choices from {self.predefine_yaml}"
                                )
                                self._logger.debug(
                                    f"Predefined choices: {predefined_choices}"
                                )
                            else:
                                self._logger.warning(
                                    f"YAML file {self.predefine_yaml} contains no data"
                                )
                        except yaml.YAMLError as e:
                            self._logger.error(
                                f"Invalid YAML format in {self.predefine_yaml}: {e}"
                            )
            except Exception as e:
                self._logger.error(f"Failed to load predefined choices: {e}")
        else:
            self._logger.info(
                "No predefined choices file provided, using default behavior"
            )

        self.main_g = flow.run
        self.triggers = [dbhh, flow, llm_nar, llm_ply]


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Run DBH scene with optional predefined choices"
    )
    parser.add_argument(
        "--predefine",
        dest="predefine_yaml",
        type=str,
        help="Path to YAML file containing predefined choices",
    )

    args = parser.parse_args()

    # Create scenario instance
    scen = Scen(predefine_yaml=args.predefine_yaml)

    sys.exit(scen.run())
