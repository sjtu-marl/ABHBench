import json
import os
import random
import re
import time
from collections import deque
from typing import Dict, List

import networkx as nx
from PIL.Image import Image

from core.event import EventDispatcher, EventSystemCallbackDropEvent
from core.log import get_logger
from core.scenario import ScenarioCompleteEvent
from DBHHelper.events import (
    ActEvent,
    ActionEvent,
    ObsEvent,
    ObsWithActEvent,
    ObsWithContextAndChoicesEvent,
    ObsWithContextEvent,
)


class DCPlayer(EventDispatcher):
    def __init__(self, output_dir: str, graph: nx.DiGraph = None) -> None:
        super().__init__()
        self._logger = get_logger()

        # Node tracking for edge information (aligned with DCollector graph structure)
        self._current_node = "root"  # Start from root node like DCollector
        self._choice_records = []  # Combined choice and edge records for DCollector

        # Obs saving tracking
        self._current_edge_folder = None
        self._obs_counter = 0
        self._skip_current_edge = False

        # Set output directory (required)
        self._output_dir = output_dir

        # Initialize root folder for initial obs saving
        self._current_edge_folder = self._create_edge_subfolder("root", None)

        # Store graph reference for exploration logic
        self._graph = graph

        self._logger.info(f"DCPlayer initialized with output directory: {output_dir}")

    @EventDispatcher.on(
        [ObsEvent, ObsWithActEvent, ObsWithContextEvent, ObsWithContextAndChoicesEvent]
    )
    def save_obs(
        self, obs: Image, act: str = None, context: str = None, choices: dict = None
    ):
        saved_path = self._save_obs_to_edge_folder(obs, act, context, choices)

        # Log with appropriate message based on what data was provided
        log_parts = ["obs"]
        if act is not None:
            log_parts.append("act")
        if context is not None:
            log_parts.append("context")
        if choices is not None:
            log_parts.append("choices")

        self._logger.debug(f"Saved {' and '.join(log_parts)} to: {saved_path}")

        return EventSystemCallbackDropEvent()

    @EventDispatcher.on(ActEvent)
    def choose(
        self,
        key: str,
        context: str,
        choices: dict,
        info: dict,
    ) -> ActionEvent:
        self._logger.info(f"Context: {context}\nChoices: {choices}")

        # Select choice based on graph exploration logic
        choice = self._select_choice_from_graph(key, choices)

        choice_text = choices[choice]

        # Update current node name - ID generation now handled in DBHHelper/flow.py
        self._current_node = key

        # Extract original key from modified key (format: original_key_id)
        # ID always exists, so split from the right
        original_key, combined_id = key.rsplit("_", 1)

        # Record combined choice and edge information
        choice_record = {
            "choices": choices,
            "selected_choice": choice,
            "selected_text": choice_text,
            "current_node": self._current_node,
            "info": info,
        }
        self._choice_records.append(choice_record)

        self._logger.info(f"Choice: {choice} {choice_text}")
        self._logger.info(f"Edge folder: {original_key}/{combined_id}/{choice}")

        # Mark current edge folder as completed before switching to a new one
        self._mark_edge_folder_completed()

        # Create subfolder for this edge (handles checking for completion marker and info validation)
        self._current_edge_folder = self._create_edge_subfolder(choice, info)
        self._obs_counter = 0

        return ActionEvent(kwargs={"choice_key": choice, "choice_text": choice_text})

    def _select_choice_from_graph(self, key: str, choices: dict) -> str:
        """
        Select choice based on graph exploration logic.

        First check if current node has unexplored choices, then use BFS to search
        for any child node with unexplored choices.
        If found, select the first unexplored choice that matches available choices.
        Otherwise, select the first available choice.

        Args:
            key: Current node key
            choices: Available choices dict

        Returns:
            Selected choice key
        """
        if not self._graph:
            return list(choices.keys())[0]

        # Find the current node in the graph
        if key in self._graph:
            node_data = self._graph.nodes[key]

            # First check if current node itself has unexplored choices
            unexplored_choices = node_data.get("unexplored_choices", [])
            if unexplored_choices:
                for unexplored_text in unexplored_choices:
                    for choice_key, choice_text in choices.items():
                        if choice_text == unexplored_text:
                            self._logger.info(
                                f"Current node has unexplored choice: {choice_key} ({choice_text})"
                            )
                            return choice_key

            # If current node has no unexplored choices, use BFS to search children
            choice_key = self._bfs_search_unexplored_choices_in_graph(key, choices)
            if choice_key:
                choice_text = choices.get(choice_key, "")
                self._logger.info(
                    f"BFS found unexplored choice: {choice_key} ({choice_text})"
                )
                return choice_key

        # Either node doesn't exist in graph or no unexplored choices found
        # Fall back to selecting first available choice
        return list(choices.keys())[0]

    def _bfs_search_unexplored_choices_in_graph(
        self, start_node_id: str, choices: dict
    ) -> str:
        """
        Use BFS to search successor nodes for any with unexplored choices.
        When found, trace back using predecessors to determine which choice the start_node should make.

        Args:
            start_node_id: The starting node ID for BFS search
            choices: Available choices dict

        Returns:
            Selected choice key if found, None otherwise
        """
        # Use BFS to search successor nodes for unexplored choices
        queue = deque(self._graph.successors(start_node_id))

        while queue:
            current_node_id = queue.popleft()
            current_node_data = self._graph.nodes[current_node_id]

            # Check if this node has unexplored choices
            unexplored_choices = current_node_data.get("unexplored_choices", [])
            if unexplored_choices:
                self._logger.info(
                    f"Found unexplored choices in node: {current_node_id}, unexplored: {unexplored_choices}"
                )

                # Trace back to start_node using predecessors
                # Find which choice from start_node leads to this unexplored node
                path_to_unexplored = nx.shortest_path(
                    self._graph, start_node_id, current_node_id
                )
                self._logger.debug(
                    f"Path to unexplored node {current_node_id}: {path_to_unexplored}"
                )

                # Get the direct child of start_node in the path
                direct_child_id = path_to_unexplored[1]
                self._logger.debug(
                    f"Direct child of {start_node_id}: {direct_child_id}"
                )

                # Find which choice text leads to this direct child
                start_node_data = self._graph.nodes[start_node_id]
                choice_to_child = start_node_data.get("choice_to_child", {})
                self._logger.debug(
                    f"choice_to_child mapping for {start_node_id}: {choice_to_child}"
                )

                found_match = False
                for choice_text, child_node_name in choice_to_child.items():
                    self._logger.debug(
                        f"Checking choice_text '{choice_text}' -> child_node_name '{child_node_name}' vs direct_child_id '{direct_child_id}'"
                    )
                    if child_node_name == direct_child_id:
                        self._logger.debug(
                            f"Found matching child node! Looking for choice_text '{choice_text}' in available choices: {list(choices.keys())}"
                        )
                        # Find the choice key that corresponds to this text
                        for choice_key, choice_text_check in choices.items():
                            self._logger.debug(
                                f"Comparing choice_text '{choice_text}' with available choice '{choice_key}': '{choice_text_check}'"
                            )
                            if choice_text_check == choice_text:
                                self._logger.info(
                                    f"Backtraced to choice: {choice_key} ({choice_text}) leading to unexplored node: {current_node_id}"
                                )
                                found_match = True
                                return choice_key

                        if not found_match:
                            self._logger.warning(
                                f"Found child mapping but no matching choice text! choice_text='{choice_text}' not found in available choices: {choices}"
                            )

                if not found_match:
                    self._logger.warning(
                        f"No matching child node found! direct_child_id='{direct_child_id}' not found in choice_to_child mapping: {choice_to_child}"
                    )

                # If we reach here, we found unexplored choices but couldn't map back to available choices
                raise ValueError(
                    f"Found unexplored choices in node '{current_node_id}' but failed to map back to available choices. "
                    f"direct_child_id='{direct_child_id}', choice_to_child={choice_to_child}, available_choices={list(choices.keys())}"
                )

            # Add successors to queue for further exploration
            queue.extend(self._graph.successors(current_node_id))

        return None

    def _create_edge_subfolder(self, choice_key: str, info: dict = None) -> str:
        """Create edge subfolder with content checking and info validation: original_key/combined_id/choice_key or root"""
        if choice_key == "root":
            # Handle root folder
            subfolder_path = os.path.join(self._output_dir, "root")
        else:
            # Extract original key and combined_id from modified key
            # ID always exists, so split from the right
            original_key, combined_id = self._current_node.rsplit("_", 1)

            # Create three-layer structure: original_key/combined_id/choice_key
            original_folder = original_key
            combined_id_folder = combined_id
            choice_folder = choice_key
            subfolder_path = os.path.join(
                self._output_dir, original_folder, combined_id_folder, choice_folder
            )

        # Handle info file - save in combined_id level (node level) for non-root
        if choice_key != "root" and info is not None:
            combined_id_folder_path = os.path.join(
                self._output_dir, original_folder, combined_id_folder
            )
            info_file = os.path.join(combined_id_folder_path, "info.json")

            # Ensure combined_id folder exists
            os.makedirs(combined_id_folder_path, exist_ok=True)

            # Check if info file already exists and compare
            if os.path.exists(info_file):
                with open(info_file, "r", encoding="utf-8") as f:
                    existing_info = json.load(f)

                if existing_info != info:
                    raise Exception(
                        f"Info mismatch for node {original_folder}/{combined_id_folder}.\n"
                        f"Node info file: {info_file}\n"
                        f"Expected: {info}\n"
                        f"Found: {existing_info}"
                    )
            else:
                # Save new info file
                with open(info_file, "w", encoding="utf-8") as f:
                    json.dump(info, f, ensure_ascii=False, indent=2)
                self._logger.info(f"Saved info to: {info_file}")

        # Check if edge folder has a completion marker, if so skip saving
        marker_file = os.path.join(subfolder_path, ".edge_completed")
        if os.path.exists(marker_file):
            self._logger.info(
                f"Edge folder {subfolder_path} has completion marker, skipping obs saving for this edge"
            )
            self._skip_current_edge = True
            # Still return the path for reference
        else:
            self._skip_current_edge = False
            # Create subfolder
            os.makedirs(subfolder_path, exist_ok=True)
            self._logger.info(f"Created edge subfolder: {subfolder_path}")

        return subfolder_path

    def _mark_edge_folder_completed(self) -> None:
        """Create a completion marker file in the current edge folder."""
        if self._current_edge_folder and os.path.exists(self._current_edge_folder):
            marker_file = os.path.join(self._current_edge_folder, ".edge_completed")
            with open(marker_file, "w") as f:
                f.write(f"Completed at: {time.time()}\n")
            self._logger.debug(f"Created edge completion marker at: {marker_file}")

    def _save_obs_to_edge_folder(
        self, obs: Image, act: str = None, context: str = None, choices: dict = None
    ) -> str:
        """Save observation image to current edge subfolder with sequential naming"""
        # Skip saving if current edge already has content
        if self._skip_current_edge:
            return None

        try:
            # Generate filename with sequential numbering
            self._obs_counter += 1
            filename = f"obs_{self._obs_counter:04d}.png"
            file_path = os.path.join(self._current_edge_folder, filename)

            # Save the image
            obs.save(file_path, "PNG")

            # Create metadata file
            metadata = {
                "filename": filename,
                "obs_counter": self._obs_counter,
                "timestamp": time.time(),
                "current_node": self._current_node,
                "edge_folder": os.path.basename(self._current_edge_folder),
            }

            # Add optional information
            if act is not None:
                metadata["act"] = act
            if context is not None:
                metadata["context"] = context
            if choices is not None:
                metadata["choices"] = choices

            # Save metadata
            metadata_filename = f"obs_{self._obs_counter:04d}_meta.json"
            metadata_path = os.path.join(self._current_edge_folder, metadata_filename)
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            self._logger.info(f"Saved obs: {filename} (#{self._obs_counter})")
            return file_path

        except Exception as e:
            self._logger.error(f"Failed to save obs to edge folder: {e}")
            raise

    @EventDispatcher.on(ScenarioCompleteEvent)
    def close(self):
        """Handle scenario completion by marking the final edge folder as completed."""
        self._logger.info("Scenario completed, marking final edge folder as completed")
        self._mark_edge_folder_completed()
