import argparse
import gc
import os

import rich

from ABHBench.dcollect.collector import DCollector
from core.log import get_logger
from core.scenario import Scenario, ScenarioCompleteEvent, ScenarioNotCompletedEvent
from DBHHelper.helper import DBHHelper
from DBHHelper.utils import get_flow_info, read_flow_cfg


class DCScene(Scenario):
    def __init__(self, collector, llm_ply):
        self.scen_name = "DBH DCollect"
        # Get Flow info at runtime
        Flow, CHAPTER_STR = get_flow_info()
        self.run_name = f"flow_{CHAPTER_STR}"
        self._logger = get_logger()
        self._is_completed = False
        self.collector = collector

        # Set the player
        self.llm_ply = llm_ply

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
        self.main_g = flow.run
        # llm_ply is already set in __init__, add it to triggers
        self.triggers = [dbhh, flow, self.llm_ply]

    def close(self):
        """Override close to prevent logger closure, as logger is managed by DCollector"""
        self._logger.info("Closing scenario")
        try:
            if hasattr(self, "event_system"):
                self.event_system.close_generators()
                with rich.get_console().status(
                    "[bold blue]Closing Event System..."
                ) as status:
                    if self._is_completed:
                        self.event_system.one_event(ScenarioCompleteEvent(), "Scenario")
                    else:
                        self.event_system.one_event(
                            ScenarioNotCompletedEvent(), "Scenario"
                        )
                    self.event_system.close()
        except Exception:
            self._logger.error("Error closing event system", exc_info=True)
        except KeyboardInterrupt:
            self._logger.info("Keyboard interrupt")
        # Do NOT call close_logger() here - logger is managed by DCollector
        gc.collect()


if __name__ == "__main__":
    import sys

    # Get Flow info at runtime
    Flow, CHAPTER_STR = get_flow_info()

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run Data Collection for DBH scene")
    parser.add_argument(
        "--output-dir",
        type=str,
        default=f"datasets/dataset_flow_{CHAPTER_STR}",
        help="Output directory for tree structure data",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum number of iterations to run (default: unlimited)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        default=False,
        help="Only show warning on hash mismatch instead of raising error",
    )
    args = parser.parse_args()

    # Use Flow class directly instead of file path
    dcollector = DCollector(
        args.output_dir, DCScene, Flow, max_iterations=args.max_iterations, verify_hash=not args.no_verify
    )

    sys.exit(dcollector.run())
