import hashlib
import inspect
import json
import logging
import os
import time
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional

import networkx as nx

from ABHBench.dcollect.player import DCPlayer
from core.log import close_logger, init_global_logger
from DBHHelper.utils import get_flow_cfg_path, get_flow_info


class DCollector:
    def __init__(
        self,
        output_dir: str,
        scene_class,
        flow_class: type,
        max_iterations: int = None,
        verify_hash: bool = True,
    ):
        self.output_dir = output_dir
        self.scene_class = scene_class
        self.flow_class = flow_class
        self.max_iterations = max_iterations
        self.verify_hash = verify_hash

        # Initialize global logger
        # Get flow info at runtime to avoid import order issues
        _, CHAPTER_STR = get_flow_info()
        self._logger = init_global_logger(
            "DBH DCollect",
            f"flow_{CHAPTER_STR}",
            levels=(
                logging.DEBUG
                if os.getenv("flags.console_debug", "false").lower() == "true"
                else logging.INFO,
                logging.INFO,
                logging.DEBUG,
            ),
            tags=["DBH", "DCollect"],
        )

    def run(self):
        """Run tree exploration loop with proper cleanup handling"""
        try:
            return self._run()
        except KeyboardInterrupt:
            self._logger.info(
                "Received keyboard interrupt, shutting down gracefully..."
            )
            return 1
        except Exception as e:
            self._logger.error(f"Unexpected error during execution: {e}")
            raise
        finally:
            # Always ensure logger is closed, even on interruption
            try:
                close_logger()
                print("Logger closed successfully")
            except Exception as e:
                print(f"Warning: Failed to close logger: {e}")
            return 1

    def _run(self):
        """Internal run method - actual tree exploration loop"""
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

        # Load existing graph if available
        existing_graph = self._load_existing_graph()
        if existing_graph:
            graph = existing_graph
        else:
            graph = nx.DiGraph()
            # Add root node with attributes
            graph.add_node("root", choice_to_child={})

        # Process flow configuration at the beginning of run - flow_class is required
        # Pass the graph so exploration progress can be calculated correctly
        self._process_flow_config(graph)

        iteration = 0
        while True:
            iteration += 1
            # Check if max iterations reached
            if self.max_iterations is not None and iteration > self.max_iterations:
                self._logger.info(
                    f"Maximum iterations ({self.max_iterations}) reached. Stopping exploration."
                )
                break

            self._logger.info(f"Starting exploration iteration {iteration}")

            # Check if exploration is complete
            if not self._has_unexplored_choices(graph):
                self._logger.info(
                    "No more unexplored paths found. Graph exploration complete."
                )
                break

            # Create and configure DCPlayer with the required output_dir and graph
            configured_player = DCPlayer(output_dir=self.output_dir, graph=graph)

            # Initialize the scene with collector and player
            scene = self.scene_class(collector=self, llm_ply=configured_player)

            # Run the scene
            result = scene.run()
            if result != 0:
                self._logger.error(f"Scene execution failed with return code: {result}")
                return result

            # Process the choice records and modify existing graph structure
            self._build_graph_structure(scene.llm_ply._choice_records, graph)

            # Save the graph structure after each iteration
            self._save_graph_structure(graph)

            # Update meta information with current exploration progress
            self._update_meta_exploration_progress(graph)

            time.sleep(10)  # Delay between iterations for stability

        return 0

    def _process_flow_config(self, graph: nx.DiGraph):
        """Process flow configuration and save metadata"""
        if self.flow_class is None:
            raise ValueError("flow_class is required but was not provided")

        try:
            flow_hash = self._compute_flow_hash(self.flow_class)
            flow_cfg_hash = self._compute_flow_cfg_hash()
            flow_identifier = f"{self.flow_class.__module__}.{self.flow_class.__name__}"

            # Check flow hash consistency before saving meta
            meta_path = os.path.join(self.output_dir, "meta.json")
            should_skip_update = not self._check_flow_hash_consistency(
                meta_path, flow_hash, flow_cfg_hash, strict_mode=self.verify_hash
            )
            if should_skip_update:
                return

            self._save_flow_meta(flow_identifier, flow_hash, flow_cfg_hash, graph)
            self._logger.info(f"Flow class processed: {flow_identifier}")
        except Exception as e:
            self._logger.error(f"Failed to process flow configuration: {e}")
            raise

    def _compute_flow_hash(self, flow_class: type) -> str:
        """
        Compute SHA256 hash of the Flow class source code using inspect.getsource().

        Args:
            flow_class: Flow class

        Returns:
            SHA256 hash of the flow source code as hexadecimal string
        """
        try:
            # Get the source code of the Flow class
            flow_source = inspect.getsource(flow_class)

            # Compute SHA256 hash
            hash_obj = hashlib.sha256(flow_source.encode("utf-8"))
            return hash_obj.hexdigest()

        except Exception as e:
            self._logger.error(
                f"Failed to compute flow hash from class {flow_class}: {e}"
            )
            raise

    def _compute_flow_cfg_hash(self) -> str:
        """
        Compute SHA256 hash of the Flow cfg file content.

        Returns:
            SHA256 hash of the flow cfg content as hexadecimal string
        """
        try:
            # Get flow info at runtime to avoid import order issues
            _, CHAPTER_STR = get_flow_info()
            flow_cfg_filename = f"flow_{CHAPTER_STR}.yaml"

            # Get config file path using the utility function
            config_file = get_flow_cfg_path(flow_cfg_filename)

            # Read file content directly
            with open(config_file, "r", encoding="utf-8") as f:
                cfg_content = f.read()

            # Compute hash from raw file content
            hash_obj = hashlib.sha256(cfg_content.encode("utf-8"))
            return hash_obj.hexdigest()

        except Exception as e:
            self._logger.error(f"Failed to compute flow cfg hash: {e}")
            raise

    def _check_flow_hash_consistency(
        self,
        meta_path: str,
        flow_hash: str,
        flow_cfg_hash: str,
        strict_mode: bool = True,
    ) -> bool:
        """
        Check if existing meta file has consistent hash values with current flow.

        Args:
            meta_path: Path to the meta.json file
            flow_hash: Current flow class hash
            flow_cfg_hash: Current flow config hash
            strict_mode: If True, raise exception on mismatch; if False, only log warning

        Returns:
            True if hashes are consistent or no existing meta file, False otherwise

        Raises:
            ValueError: If hash mismatch is detected and strict_mode is True
        """
        if not os.path.exists(meta_path):
            return True

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                existing_meta = json.load(f)

            existing_flow_hash = existing_meta.get("flow_info", {}).get("flow_hash")
            existing_cfg_hash = existing_meta.get("flow_info", {}).get("flow_cfg_hash")

            # Check both flow class hash and flow cfg hash
            flow_hash_match = existing_flow_hash == flow_hash
            cfg_hash_match = existing_cfg_hash == flow_cfg_hash

            if flow_hash_match and cfg_hash_match:
                self._logger.info(
                    f"Flow hash and cfg hash unchanged (flow: {flow_hash}, cfg: {flow_cfg_hash}), skipping meta update"
                )
                return False
            else:
                # Hash mismatch detected
                mismatch_details = []
                if not flow_hash_match:
                    mismatch_details.append(
                        f"Flow class hash - Existing: {existing_flow_hash if existing_flow_hash else 'None'}, Current: {flow_hash}"
                    )
                if not cfg_hash_match:
                    mismatch_details.append(
                        f"Flow cfg hash - Existing: {existing_cfg_hash if existing_cfg_hash else 'None'}, Current: {flow_cfg_hash}"
                    )

                message = (
                    f"Hash mismatch detected! {'; '.join(mismatch_details)}. "
                    f"This indicates the flow class or configuration has changed."
                )

                if strict_mode:
                    # Raise exception to prevent running with different flow/config
                    raise ValueError(
                        f"{message} Please use a different output directory or remove existing data."
                    )
                else:
                    # Only log warning and continue
                    self._logger.warning(f"{message} Continuing with existing data.")
                    return True

        except json.JSONDecodeError as e:
            self._logger.warning(
                f"Failed to read existing meta.json: {e}, will create new one"
            )
            return True
        except Exception:
            raise

    def _save_flow_meta(
        self,
        flow_identifier: str,
        flow_hash: str,
        flow_cfg_hash: str,
        graph: nx.DiGraph,
    ):
        """
        Save flow metadata to meta.yaml file in output directory.
        Check if existing meta has the same hash, and only write if different.

        Args:
            flow_identifier: Flow class identifier (module.class_name)
            flow_hash: SHA256 hash of the flow source code
            graph: Graph for exploration progress calculation
        """
        try:
            meta_path = os.path.join(self.output_dir, "meta.json")

            # Calculate exploration progress from graph
            explored_nodes, total_nodes = self._get_graph_exploration_stats(graph)
            exploration_progress = f"{explored_nodes}/{total_nodes}"
            self._logger.info(f"Current exploration progress: {exploration_progress}")

            # Prepare metadata for Flow class
            # Get flow info at runtime to avoid import order issues
            _, CHAPTER_STR = get_flow_info()
            flow_info = {
                "flow_class": flow_identifier,
                "flow_hash": flow_hash,
                "flow_cfg_hash": flow_cfg_hash,
                "hash_algorithm": "SHA256",
                "chapter_number": getattr(self.flow_class, "chapter_number", None),
                "obs_interval": int(os.getenv("agent.obs_interval", 10)),
                "obs_move_interval": int(os.getenv("agent.obs_move_interval", 30)),
            }

            meta_data = {
                "flow_info": flow_info,
                "collection_info": {
                    "timestamp": datetime.now().isoformat(),
                    "output_directory": self.output_dir,
                    "chapter": CHAPTER_STR,
                    "exploration_progress": exploration_progress,
                },
            }

            # Save metadata to JSON file
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta_data, f, ensure_ascii=False, indent=2)

            self._logger.info(f"Flow metadata saved to: {meta_path}")

        except Exception as e:
            self._logger.error(f"Failed to save flow metadata: {e}")
            raise

    def _update_meta_exploration_progress(self, graph: nx.DiGraph):
        """
        Update exploration progress in existing meta.json file.

        Args:
            graph: Graph for exploration progress calculation
        """
        try:
            meta_path = os.path.join(self.output_dir, "meta.json")

            if not os.path.exists(meta_path):
                self._logger.warning(
                    "meta.json not found, cannot update exploration progress"
                )
                return

            # Read existing meta data
            with open(meta_path, "r", encoding="utf-8") as f:
                meta_data = json.load(f)

            # Calculate current exploration progress
            explored_nodes, total_nodes = self._get_graph_exploration_stats(graph)
            exploration_progress = f"{explored_nodes}/{total_nodes}"

            # Update exploration progress and timestamp
            if "collection_info" not in meta_data:
                meta_data["collection_info"] = {}

            meta_data["collection_info"]["exploration_progress"] = exploration_progress
            meta_data["collection_info"]["last_updated"] = datetime.now().isoformat()

            # Save updated meta data
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta_data, f, ensure_ascii=False, indent=2)

            self._logger.info(f"Updated exploration progress: {exploration_progress}")

        except Exception as e:
            self._logger.error(f"Failed to update meta exploration progress: {e}")

    def _build_graph_structure(self, choice_records: List[Dict], graph: nx.DiGraph):
        """Build a graph structure from choice records using current_node approach"""
        # Build graph sequentially following the choice path
        current_parent_id = "root"

        for i, record in enumerate(choice_records):
            all_choices = record["choices"]
            selected_choice = record["selected_choice"]
            selected_text = record["selected_text"]
            current_node_id = record["current_node"]
            info = record["info"]  # Get info from choice record

            # Check if node already exists in graph
            if current_node_id in graph:
                # Node already exists, update its choice information
                node_data = graph.nodes[current_node_id]
                # Assert that all_choices matches previously recorded available_choices
                assert all_choices == node_data["available_choices"], (
                    f"Choices mismatch for node '{current_node_id}'.\n"
                    f"Current choices: {all_choices}\n"
                    f"Previously recorded available_choices: {node_data['available_choices']}"
                )
                # Assert that the selected choice is in available choices
                assert selected_text in node_data["available_choices"].values(), (
                    f"Selected choice '{selected_text}' not found in available choices: {node_data['available_choices']}"
                )
                if selected_text not in node_data["explored_choices"]:
                    node_data["explored_choices"].append(selected_text)
                if selected_text in node_data["unexplored_choices"]:
                    node_data["unexplored_choices"].remove(selected_text)
            else:
                # Create new node for this current_node
                graph.add_node(
                    current_node_id,
                    available_choices=all_choices,
                    explored_choices=[selected_text],
                    unexplored_choices=[
                        choice
                        for choice in all_choices.values()
                        if choice != selected_text
                    ],
                    level=i,
                    choice_to_child={},  # Initialize choice_to_child mapping
                    info=info,  # Record info in node
                )

            # Add edge from parent to current node and update choice mapping
            if i == 0:
                # First node: connect from root without choice text (root has no choices)
                # Root node should have only one child - the first node
                
                if not graph.has_edge(current_parent_id, current_node_id):
                    graph.add_edge(current_parent_id, current_node_id)
                
                # Assert that root has exactly one child and it's the current first node
                root_children = list(graph.successors("root"))
                assert len(root_children) == 1 and root_children[0] == current_node_id, (
                    f"Root node should have exactly one child (the first node '{current_node_id}'), "
                    f"but found children: {root_children}"
                )
            else:
                # Subsequent nodes: use selected_text from previous record
                choice_text_for_edge = choice_records[i-1]["selected_text"]
                
                # Update parent node's choice_to_child mapping
                parent_data = graph.nodes[current_parent_id]

                # Check if choice is already mapped
                if choice_text_for_edge in parent_data["choice_to_child"]:
                    existing_mapping = parent_data["choice_to_child"][choice_text_for_edge]
                    # If mapping exists but points to different node, raise error
                    if existing_mapping != current_node_id:
                        raise AssertionError(
                            f"Choice '{choice_text_for_edge}' from parent node '{current_parent_id}' already mapped to child '{existing_mapping}', cannot map to '{current_node_id}'"
                        )
                else:
                    # Map the choice text to the current node ID
                    parent_data["choice_to_child"][choice_text_for_edge] = current_node_id

                    # Add edge if it doesn't exist
                    if not graph.has_edge(current_parent_id, current_node_id):
                        graph.add_edge(
                            current_parent_id,
                            current_node_id,
                            choice_text=choice_text_for_edge,
                        )

            # Prepare for next iteration
            current_parent_id = current_node_id

    def _load_existing_graph(self) -> Optional[nx.DiGraph]:
        """Load existing graph structure from JSON file if it exists"""
        json_path = os.path.join(self.output_dir, "choice_graph.json")

        if not os.path.exists(json_path):
            self._logger.info("No existing graph structure found")
            return None

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                graph_data = json.load(f)

            if graph_data:
                graph = nx.node_link_graph(graph_data, directed=True)
                self._logger.info(f"Loaded existing graph structure from: {json_path}")
                return graph
            else:
                self._logger.warning("Empty graph structure file")
                return None

        except Exception as e:
            self._logger.error(f"Failed to load existing graph structure: {e}")
            return None

    def _save_graph_structure(self, graph: nx.DiGraph):
        """Save the graph structure to output directory as JSON"""
        # Convert graph to dictionary using NetworkX
        graph_data = nx.node_link_data(graph)

        # Save as JSON
        json_path = os.path.join(self.output_dir, "choice_graph.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)

        self._logger.info(f"Graph structure saved to: {json_path}")

        # Output graph structure for debugging
        self._output_graph_structure(graph)

    def _get_graph_exploration_stats(self, graph: nx.DiGraph) -> tuple[int, int]:
        """
        Calculate exploration statistics for the graph.

        Args:
            graph: The graph structure

        Returns:
            tuple: (explored_choices, total_choices) for all nodes
        """
        if not graph:
            return 0, 0

        explored_count = 0
        total_count = 0

        # Traverse all nodes in the graph (skip root node)
        for node_id in graph.nodes():
            if node_id == "root":
                continue

            node_data = graph.nodes[node_id]

            # Count choices in all non-root nodes
            # Count total available choices
            available_choices = node_data.get("available_choices", {})
            total_count += len(available_choices)

            # Count explored choices
            explored_choices = node_data.get("explored_choices", [])
            explored_count += len(explored_choices)

        return explored_count, total_count

    def _output_graph_structure(self, graph: nx.DiGraph):
        """Output graph structure for debugging"""
        self._logger.debug("Graph structure:")

        # Output nodes information
        for node_id in graph.nodes():
            node_data = graph.nodes[node_id]
            node_info = f"Node {node_id}"

            # Show exploration info for non-root nodes
            if node_id != "root":
                explored = len(node_data.get("explored_choices", []))
                unexplored = len(node_data.get("unexplored_choices", []))
                node_info += f" (explored: {explored}, unexplored: {unexplored})"

            # Show choice_to_child mapping for debugging
            choice_to_child = node_data.get("choice_to_child", {})
            if choice_to_child:
                choice_mapping = ", ".join(
                    [
                        f"'{choice}'->{child}"
                        for choice, child in choice_to_child.items()
                    ]
                )
                node_info += f" [choices: {choice_mapping}]"
            self._logger.debug(node_info)

    def _has_unexplored_choices(self, graph: nx.DiGraph) -> bool:
        """
        Check if there are any unexplored choices in the graph.

        Returns:
            True: There are unexplored choices remaining
            False: No more unexplored choices (exploration complete)
        """
        if not graph:
            return False

        # Check if graph only has root (no other nodes) - first exploration case
        if len(graph.nodes()) <= 1:
            return True

        # Find any node with unexplored choices (skip root node)
        for node_id in graph.nodes():
            if node_id == "root":
                continue

            node_data = graph.nodes[node_id]

            # Check if this node has unexplored choices
            if node_data.get("unexplored_choices", []):
                return True

        # No unexplored choices found
        return False
