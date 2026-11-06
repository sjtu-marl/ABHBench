import json
from pathlib import Path
from typing import override

import networkx as nx
from PIL import Image

from ABHBench.deval.dummy_api import DBHHelperDummyAPI
from core.event import EventDispatcher, EventSystem, EventSystemCloseEvent
from core.log import get_logger
from core.transform import register_auto_yield
from core.utils import DictConfig
from DBHHelper.events import (
    ActEvent,
    ActionEvent,
    ObsEvent,
    ObsWithActEvent,
    ObsWithContextAndChoicesEvent,
    ObsWithContextEvent,
)


class DEvalHelper(
    DictConfig,
    DBHHelperDummyAPI,
    EventDispatcher,
):
    def __init__(self, cfg, datasets_dir):
        self._logger = get_logger()
        self.set_cfg(cfg)
        self.datasets_dir = datasets_dir

        # Graph navigation state
        self._graph = None
        self._current_node_id = None
        self._current_obs_iterator = None
        self._current_obs_list = []
        self._current_obs_index = 0

        # Simplified navigation state
        self._current_key = "root"
        self._current_choice_key = None

    @override
    def setup(self):
        if self.datasets_dir:
            if self._validate_datasets():
                self._load_choice_graph()
                self._initialize_navigation()
            else:
                raise ValueError("Dataset validation failed")

    def _validate_datasets(self):
        """Validate that the datasets directory contains complete collection data"""
        if not self.datasets_dir:
            self._logger.warning("No datasets directory specified")
            return False

        datasets_path = Path(self.datasets_dir)
        if not datasets_path.exists():
            self._logger.error(
                f"Datasets directory does not exist: {self.datasets_dir}"
            )
            return False

        self._logger.info(f"Validating datasets directory: {self.datasets_dir}")

        # Check required files
        validation_results = {
            "meta_json": self._validate_meta_json(datasets_path),
            "choice_graph": self._validate_choice_graph(datasets_path),
            "obs_folders": self._validate_obs_folders(datasets_path),
        }

        # Report validation results
        for check, result in validation_results.items():
            status = "✓" if result else "✗"
            self._logger.info(f"{status} {check}: {'PASS' if result else 'FAIL'}")

        all_valid = all(validation_results.values())
        if all_valid:
            self._logger.info("✓ Datasets validation completed successfully")
        else:
            self._logger.warning("⚠ Some datasets validation checks failed")

        return all_valid

    def _validate_meta_json(self, datasets_path: Path) -> bool:
        """Check if meta.json exists and contains required information"""
        meta_path = datasets_path / "meta.json"
        if not meta_path.exists():
            self._logger.error("meta.json not found")
            return False

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta_data = json.load(f)

            # Check required fields
            required_fields = ["flow_info", "collection_info"]
            for field in required_fields:
                if field not in meta_data:
                    self._logger.error(f"meta.json missing required field: {field}")
                    return False

            # Check exploration progress
            collection_info = meta_data.get("collection_info", {})
            exploration_progress = collection_info.get("exploration_progress", "0/0")

            if "/" in exploration_progress:
                try:
                    explored, total = exploration_progress.split("/")
                    explored_count = int(explored)
                    total_count = int(total)

                    if total_count > 0:
                        completion_rate = explored_count / total_count * 100
                        self._logger.info(
                            f"Collection progress: {exploration_progress} ({completion_rate:.1f}%)"
                        )

                        if explored_count == total_count and total_count > 0:
                            self._logger.info("✓ Data collection appears complete")
                            return True
                        else:
                            self._logger.error(
                                f"⚠ Data collection incomplete: {exploration_progress}"
                            )
                            return False
                    else:
                        self._logger.error("No choices found in exploration progress")
                        return False

                except ValueError:
                    self._logger.error(
                        f"Invalid exploration progress format: {exploration_progress}"
                    )
                    return False

            self._logger.error("No valid exploration progress found")
            return False

        except json.JSONDecodeError as e:
            self._logger.error(f"Failed to parse meta.json: {e}")
            return False
        except Exception as e:
            self._logger.error(f"Error validating meta.json: {e}")
            return False

    def _validate_choice_graph(self, datasets_path: Path) -> bool:
        """Check if choice_graph.json exists and is valid, and validate edge folders"""
        graph_path = datasets_path / "choice_graph.json"
        if not graph_path.exists():
            self._logger.error("choice_graph.json not found")
            return False

        try:
            with open(graph_path, "r", encoding="utf-8") as f:
                graph_data = json.load(f)

            if not graph_data:
                self._logger.error("choice_graph.json is empty")
                return False

            # Load graph structure and validate edge folders
            graph = nx.node_link_graph(graph_data, directed=True)

            # Check if root node exists
            if "root" not in graph:
                self._logger.error("choice_graph.json missing root node")
                return False

            self._logger.debug("Choice graph root node: root")

            # Output graph structure for debugging
            self._logger.debug("Graph structure:")
            for node_id in graph.nodes():
                node_data = graph.nodes[node_id]
                node_info = f"Node: {node_id}"
                if node_id != "root":
                    explored = len(node_data.get("explored_choices", {}))
                    unexplored = len(node_data.get("unexplored_choices", {}))
                    node_info += f" (explored: {explored}, unexplored: {unexplored})"
                self._logger.debug(node_info)

            if not self._validate_graph_edge_folders(graph, datasets_path):
                return False

            return True

        except json.JSONDecodeError as e:
            self._logger.error(f"Failed to parse choice_graph.json: {e}")
            return False
        except Exception as e:
            self._logger.error(f"Error validating choice_graph.json: {e}")
            return False

    def _check_folder_exists(
        self,
        datasets_path: Path,
        folder_name: str,
        missing_folders: list,
        checked_folders: list,
    ):
        """Helper method to check if a folder exists and update lists accordingly"""
        expected_folder_path = datasets_path / folder_name
        if not expected_folder_path.exists():
            missing_folders.append(folder_name)
            self._logger.error(f"Missing edge folder: {folder_name}")
        else:
            checked_folders.append(folder_name)
            self._logger.debug(f"Found edge folder: {folder_name}")

    def _validate_graph_edge_folders(
        self, graph: nx.DiGraph, datasets_path: Path
    ) -> bool:
        """
        Validate that all nodes in the graph have corresponding edge folders.

        Args:
            graph: The directed graph
            datasets_path: Path to the datasets directory

        Returns:
            bool: True if all edge folders exist, False otherwise
        """
        missing_folders = []
        checked_folders = []

        # Traverse all nodes and check their edge folders
        for node_id in graph.nodes():
            node_data = graph.nodes[node_id]

            # Check edge folders for all nodes
            if node_id == "root":
                # Only root has its own folder
                self._check_folder_exists(
                    datasets_path, node_id, missing_folders, checked_folders
                )
            else:
                # For non-root nodes, check child folders based on available choices
                available_choices = node_data.get("available_choices", {})
                if available_choices:  # Only process nodes with choices
                    original_key, combined_id = node_id.rsplit("_", 1)

                    # For each choice, check if the corresponding folder exists
                    # Use the same format as player.py: original_key/combined_id/choice_key (3-layer structure)
                    for choice_key in available_choices.keys():
                        child_folder_path = f"{original_key}/{combined_id}/{choice_key}"
                        self._check_folder_exists(
                            datasets_path,
                            child_folder_path,
                            missing_folders,
                            checked_folders,
                        )

        # Report validation results
        self._logger.info(f"Checked {len(checked_folders)} edge folders")
        if missing_folders:
            self._logger.error(
                f"Missing {len(missing_folders)} edge folders: {missing_folders}"
            )
            return False
        else:
            self._logger.info("✓ All edge folders exist")
            return True

    def _validate_obs_folders(self, datasets_path: Path) -> bool:
        """Check obs folders and their contents"""
        obs_folders = []
        png_count = 0
        meta_count = 0

        # Find all obs folders (should contain .png files)
        for item in datasets_path.iterdir():
            if item.is_dir():
                png_files = list(item.glob("*.png"))
                meta_files = list(item.glob("*_meta.json"))

                if png_files:  # This is an obs folder
                    obs_folders.append(item.name)
                    png_count += len(png_files)
                    meta_count += len(meta_files)

        if not obs_folders:
            self._logger.error("No observation folders found")
            return False

        self._logger.info(
            f"Found {len(obs_folders)} obs folders with {png_count} images and {meta_count} metadata files"
        )

        # Check if root folder exists (should always be there)
        root_folder = datasets_path / "root"
        if not root_folder.exists():
            self._logger.warning("Root obs folder not found")

        # Validate some folders have both images and metadata
        if png_count == 0:
            self._logger.error("No observation images found")
            return False

        if meta_count < png_count * 0.5:  # Allow some missing metadata but not too much
            self._logger.warning(f"Low metadata file count: {meta_count}/{png_count}")

        return True

    def _load_choice_graph(self):
        """Load choice graph from datasets directory"""
        graph_path = Path(self.datasets_dir) / "choice_graph.json"

        try:
            with open(graph_path, "r", encoding="utf-8") as f:
                graph_data = json.load(f)

            if graph_data:
                self._graph = nx.node_link_graph(graph_data, directed=True)
                self._logger.info(
                    f"Choice graph loaded successfully from: {graph_path}"
                )
            else:
                raise ValueError("Empty choice graph file")

        except Exception as e:
            self._logger.error(f"Failed to load choice graph: {e}")
            raise

    def _initialize_navigation(self):
        """Initialize navigation to root node"""
        if not self._graph:
            raise ValueError("Choice graph not loaded")

        self._current_node_id = "root"
        self._current_key = "root"
        self._current_choice_key = None
        self._load_current_node_obs()
        self._logger.info("Navigation initialized at root node")

    def _load_current_node_obs(self):
        """Load observation data for current node"""
        self._current_obs_list = []
        self._current_obs_index = 0

        if not self._current_node_id:
            return

        # Get folder name for current node
        folder_name = self._find_obs_folder_for_node()

        if not folder_name:
            error_msg = f"No obs folder found for node: {self._current_key}"
            self._logger.error(error_msg)
            raise ValueError(error_msg)

        obs_folder_path = Path(self.datasets_dir) / folder_name
        if not obs_folder_path.exists():
            self._logger.warning(f"Obs folder does not exist: {obs_folder_path}")
            return

        # Load all PNG files in order
        png_files = sorted(obs_folder_path.glob("*.png"))
        for png_file in png_files:
            try:
                # Load image
                image = Image.open(png_file)

                # Load optional metadata - format: obs_{counter:04d}_meta.json
                # Extract counter from PNG filename: obs_0001.png -> obs_0001_meta.json
                png_stem = png_file.stem  # e.g., "obs_0001"
                metadata_filename = f"{png_stem}_meta.json"
                metadata_file = obs_folder_path / metadata_filename

                metadata = {}
                if metadata_file.exists():
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        metadata = json.load(f)

                self._current_obs_list.append(
                    {"image": image, "metadata": metadata, "filename": png_file.name}
                )

            except Exception as e:
                self._logger.error(f"Failed to load obs file {png_file}: {e}")

        self._logger.info(
            f"Loaded {len(self._current_obs_list)} observations for node: {self._current_key}"
        )

    def _find_obs_folder_for_node(self):
        """Find the observation folder corresponding to current navigation state"""
        if self._current_key == "root":
            return "root"

        original_key, combined_id = self._current_key.rsplit("_", 1)
        # Use 3-layer structure: original_key/combined_id/choice_key
        return f"{original_key}/{combined_id}/{self._current_choice_key}"

    @register_auto_yield
    @override
    def obs(self, context=None, choices=None, choice_stage=None):
        """
        Output observations for current node.
        When choice_stage is 'before', yield all observations for current node.
        For other choice_stage values, do nothing.
        """
        # Only process when choice_stage is "before"
        if choice_stage != "before":
            return

        # Load observations for current node if not already loaded
        if not self._current_obs_list:
            self._load_current_node_obs()

        if not self._current_obs_list:
            error_msg = f"No observations available for current node: {self._current_key if self._current_key else 'None'}"
            self._logger.error(error_msg)
            raise ValueError(error_msg)

        # Yield all observations for current node
        self._logger.info(
            f"Yielding all {len(self._current_obs_list)} observations for node: {self._current_key}"
        )

        for i, obs_data in enumerate(self._current_obs_list):
            obs_image = obs_data["image"]
            metadata = obs_data["metadata"]

            self._logger.debug(
                f"Yielding obs {i + 1}/{len(self._current_obs_list)}: {self._find_obs_folder_for_node()}/{obs_data['filename']}"
            )

            # Use metadata from saved files to determine event type
            saved_context = metadata.get("context")
            saved_choices = metadata.get("choices")
            saved_act = metadata.get("act")

            # Yield appropriate event based on saved metadata
            if saved_context is not None:
                if saved_choices is not None:
                    yield ObsWithContextAndChoicesEvent(
                        kwargs={
                            "obs": obs_image,
                            "context": saved_context,
                            "choices": saved_choices,
                        }
                    )
                else:
                    yield ObsWithContextEvent(
                        kwargs={
                            "obs": obs_image,
                            "context": saved_context,
                        }
                    )
            elif saved_act is not None:
                yield ObsWithActEvent(
                    kwargs={
                        "obs": obs_image,
                        "act": saved_act,
                    }
                )
            else:
                yield ObsEvent(kwargs={"obs": obs_image})

    @register_auto_yield
    @override
    def act(
        self,
        key: str,
        context: str,
        choices: dict,
        info: dict,
    ):
        """
        Handle action selection and node navigation.
        After act is called, switch to the appropriate child node.
        """
        self._logger.debug(
            f"ACT: key={key}, context={context}, choices={choices}, info={info}"
        )
        yield ActEvent(
            kwargs={
                "key": key,
                "context": context,
                "choices": choices,
                "info": info,
            },
            callback=ActionEvent,
        )
        self._logger.debug("Waiting for action...")
        action_event: ActionEvent = yield from EventSystem.wait_for_callback()

        # Update node after receiving action_event
        self._update_node_after_action(key, action_event)

        return action_event

    def _update_node_after_action(self, key: str, action_event: ActionEvent):
        """Update navigation node after receiving action event"""
        selected_choice_key = action_event.kwargs.choice_key
        selected_choice_text = action_event.kwargs.choice_text

        self._current_obs_list = []
        self._current_obs_index = 0
        self._current_key = key
        self._current_choice_key = selected_choice_key

        self._logger.info(
            f"Switched to node: {self._current_key}, choice key: {selected_choice_key}, choice text: {selected_choice_text}"
        )

    @EventDispatcher.on(EventSystemCloseEvent)
    @override
    def close(self):
        self._logger.debug("Starting DEvalHelper close sequence")
