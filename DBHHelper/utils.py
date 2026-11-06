import codecs
import hashlib
import importlib
import json
import math
import os
import sys
from collections import defaultdict
from typing import Callable

import networkx as nx
import plotly.graph_objects as go
import yaml

from core.log import get_clearml, get_logger, is_enabled_clearml
from core.utils import Infix, InfixOpType


def dot_product(v1, v2):
    """Calculate the dot product of two vectors."""
    return sum(x * y for x, y in zip(v1, v2))


def scalar_multiply(scalar, vector):
    """Multiply a vector by a scalar."""
    return [scalar * x for x in vector]


def vector_subtract(v1, v2):
    """Subtract vector v2 from vector v1."""
    return [x - y for x, y in zip(v1, v2)]


def vector_magnitude(v):
    """Calculate the magnitude (length) of a vector."""
    return (sum(x**2 for x in v)) ** 0.5


def cross_product(v1, v2):
    x1, y1 = v1
    x2, y2 = v2
    return x1 * y2 - y1 * x2


def angle_between_vectors(v1, v2):
    """Calculate the angle in radians between two vectors."""
    dot_prod = dot_product(v1, v2)
    magnitude_v1 = vector_magnitude(v1)
    magnitude_v2 = vector_magnitude(v2)
    cos_angle = dot_prod / (magnitude_v1 * magnitude_v2)
    # Clamping the cosine value to the range [-1, 1] to avoid numerical errors
    cos_angle = max(-1, min(1, cos_angle))
    angle = math.acos(cos_angle)
    return angle


def project_to_plane(vector, normal):
    """Project a vector onto a plane defined by a normal vector."""
    # Normalize the normal vector
    normal_length = vector_magnitude(normal)
    normal_unit = [x / normal_length for x in normal]
    # Compute the component of the vector along the normal
    projection_length = dot_product(vector, normal_unit)
    # Calculate the projection of the vector onto the plane
    projection = vector_subtract(
        vector, scalar_multiply(projection_length, normal_unit)
    )
    return projection


def _multipartite_dag_layout(G: nx.DiGraph, orientation: str = "TB") -> dict:
    """Hierarchical coordinates for a *DAG* using *NetworkX*'s builtin
    :func:`multipartite_layout` (requires **no** Graphviz/pydot).

    Parameters
    ----------
    G : nx.DiGraph
        Input graph **must** be acyclic.
    orientation : {"TB", "BT", "LR", "RL"}
        Edge flow direction – Top‑Bottom, Bottom‑Top, Left‑Right, Right‑Left.

    Returns
    -------
    dict
        Mapping ``{node: (x, y)}`` compatible with Plotly.
    """
    if not nx.is_directed_acyclic_graph(G):
        raise ValueError("_multipartite_dag_layout: graph must be a DAG")

    # --- assign each node to its *generation* using builtin topological_generations ---
    subset = {
        node: layer
        for layer, generation in enumerate(nx.topological_generations(G))
        for node in generation
    }
    nx.set_node_attributes(G, subset, "subset")

    # multipartite_layout arranges nodes in equally‑spaced bands by "subset"
    align = "vertical" if orientation in {"TB", "BT"} else "horizontal"
    pos = nx.multipartite_layout(G, subset_key="subset", align=align)

    # orientation tweaks (Plotly's y‑axis increases upward)
    if orientation == "BT":  # flip vertical
        pos = {n: (x, -y) for n, (x, y) in pos.items()}
    elif orientation == "LR":  # rotate CCW 90°
        pos = {n: (y, x) for n, (x, y) in pos.items()}
    elif orientation == "RL":  # rotate CW 90° + flip
        pos = {n: (-y, x) for n, (x, y) in pos.items()}

    return pos


def draw_flowgraph(G, log_path, path=None, filename=None, logger=None):
    """
    Draw a flow graph using Plotly, with option to highlight specific paths.

    Args:
        G: NetworkX DiGraph object
        log_path: Path to save the output file
        path: List of node paths to highlight (optional)
        filename: Output filename (default depends on path: "graph.html" or "graph_highlight.html")
        logger: Logger object (optional)
    """
    # Set default filename based on whether we're highlighting a path
    if filename is None:
        filename = "graph_highlight.html" if path else "graph.html"

    if logger:
        if path:
            logger.info("Drawing highlighted flow graph")
        else:
            logger.info("Drawing flow graph")

    orientation: str = "TB"
    # Try to use DAG layout first, but fall back to cyclic layout if the graph has cycles
    try:
        pos = _multipartite_dag_layout(G, orientation)
        if logger:
            logger.info(
                "Using NetworkX multipartite_layout for DAG (orientation=%s)",
                orientation,
            )
    except ValueError:  # This will be raised if the graph is not a DAG
        pos = multipartite_layout_with_cycles(G, orientation)
        if logger:
            logger.info(
                "Using multipartite_layout_with_cycles (orientation=%s)", orientation
            )

    # Handle different visualizations based on whether path is provided
    if path:
        # Prepare node colors for highlighted path
        node_colors = ["lightgray" if node not in path else "#00bfff" for node in G]

        # Create edge traces for normal and highlighted edges with straight lines
        edge_normal = go.Scatter(
            x=[],
            y=[],
            line=dict(width=1, color="darkgray"),
            hoverinfo="none",
            mode="lines",
        )

        edge_highlight = go.Scatter(
            x=[],
            y=[],
            line=dict(width=2, color="#dc143c"),
            hoverinfo="none",
            mode="lines",
        )

        # Add edges to appropriate traces using straight lines
        for u, v in G.edges():
            x0, y0 = pos[u]
            x1, y1 = pos[v]

            is_highlighted = (
                u in path and v in path and abs(path.index(u) - path.index(v)) == 1
            )

            if is_highlighted:
                edge_highlight["x"] += (x0, x1, None)
                edge_highlight["y"] += (y0, y1, None)
            else:
                edge_normal["x"] += (x0, x1, None)
                edge_normal["y"] += (y0, y1, None)

        # Create node trace with colored nodes
        node_trace = go.Scatter(
            x=[pos[node][0] for node in G],
            y=[pos[node][1] for node in G],
            text=[node for node in G],
            textposition="middle center",
            mode="markers+text",
            hoverinfo="text",
            marker=dict(showscale=False, color=node_colors, size=30, line_width=2),
        )

        # Create figure with highlighted path
        fig = go.Figure(
            data=[edge_normal, edge_highlight, node_trace],
            layout=go.Layout(
                showlegend=False,
                hovermode="closest",
                margin=dict(b=20, l=5, r=5, t=40),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                plot_bgcolor="white",
            ),
        )

    else:
        # Create edge trace for regular graph
        edge_trace = go.Scatter(
            x=[],
            y=[],
            line=dict(width=1, color="darkgray"),
            hoverinfo="none",
            mode="lines",
        )

        # Add edges to edge trace with straight lines
        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_trace["x"] += (x0, x1, None)
            edge_trace["y"] += (y0, y1, None)

        # Create node traces for regular graph
        node_trace = go.Scatter(
            x=[pos[node][0] for node in G],
            y=[pos[node][1] for node in G],
            text=[node for node in G],
            textposition="middle center",
            mode="markers+text",
            hoverinfo="text",
            marker=dict(showscale=False, color="lightgray", size=30, line_width=2),
        )

        # Create figure for regular graph
        fig = go.Figure(
            data=[edge_trace, node_trace],
            layout=go.Layout(
                showlegend=False,
                hovermode="closest",
                margin=dict(b=20, l=5, r=5, t=40),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                plot_bgcolor="white",
            ),
        )

    # Save to file
    fig.write_html(f"{log_path}/{filename}")

    # Report to clearml if enabled
    if is_enabled_clearml():
        task = get_clearml()
        series = "highlighted_flowgraph" if path else "flowgraph"
        task.get_logger().report_plotly(
            title="flowgraph",
            series=series,
            figure=fig,
        )


def multipartite_layout_with_cycles(G: nx.DiGraph, orientation: str = "TB") -> dict:
    """Hierarchical coordinates for directed graphs (including those with cycles) using
    NetworkX's builtin multipartite_layout (requires no Graphviz/pydot).

    This function extends the functionality of _multipartite_dag_layout to handle graphs
    with cycles by identifying strongly connected components (SCCs) and assigning them
    to appropriate layers.

    Parameters
    ----------
    G : nx.DiGraph
        Input graph, can be any directed graph including those with cycles.
    orientation : {"TB", "BT", "LR", "RL"}
        Edge flow direction – Top‑Bottom, Bottom‑Top, Left‑Right, Right‑Left.

    Returns
    -------
    dict
        Mapping ``{node: (x, y)}`` compatible with Plotly.
    """
    # Step 1: Find strongly connected components (SCCs)
    sccs = list(nx.strongly_connected_components(G))

    # Step 2: Create a condensed graph where each SCC is a single node
    condensed_graph = nx.DiGraph()

    # Map each node to its SCC index
    scc_mapping = {}
    for i, component in enumerate(sccs):
        for node in component:
            scc_mapping[node] = i

    # Add nodes to the condensed graph
    for i in range(len(sccs)):
        condensed_graph.add_node(i)

    # Add edges between SCCs
    for u, v in G.edges():
        scc_u = scc_mapping[u]
        scc_v = scc_mapping[v]
        if scc_u != scc_v and not condensed_graph.has_edge(scc_u, scc_v):
            condensed_graph.add_edge(scc_u, scc_v)

    # Step 3: Assign layers to SCCs based on topology of the condensed graph
    # The condensed graph is guaranteed to be a DAG
    subset = {}

    try:
        # Try to use topological generations for the condensed graph
        layers = {
            scc_idx: layer
            for layer, generation in enumerate(
                nx.topological_generations(condensed_graph)
            )
            for scc_idx in generation
        }

        # Map layers back to original nodes
        for node in G:
            scc_idx = scc_mapping[node]
            subset[node] = layers[scc_idx]

    except nx.NetworkXUnfeasible:
        # Fallback in case there's an issue with the condensed graph
        # Use BFS from nodes with minimal in-degree
        subset = {}
        visited = set()

        # Start with nodes that have minimal in-degree
        queue = [
            (node, 0)
            for node in G
            if G.in_degree(node) == min(dict(G.in_degree()).values())
        ]

        while queue:
            node, layer = queue.pop(0)
            if node in visited:
                continue

            visited.add(node)
            subset[node] = layer

            for successor in G.successors(node):
                if successor not in visited:
                    queue.append((successor, layer + 1))

        # Handle any remaining unvisited nodes
        remaining_nodes = set(G.nodes()) - visited
        if remaining_nodes:
            max_layer = max(subset.values()) if subset else 0
            for i, node in enumerate(remaining_nodes):
                subset[node] = max_layer + 1

    # Step 4: Set the subset attribute on the nodes
    nx.set_node_attributes(G, subset, "subset")

    # Step 5: Apply multipartite_layout with the assigned subsets
    align = "vertical" if orientation in {"TB", "BT"} else "horizontal"
    pos = nx.multipartite_layout(G, subset_key="subset", align=align)

    # Apply orientation adjustments (same as in _multipartite_dag_layout)
    if orientation == "BT":  # flip vertical
        pos = {n: (x, -y) for n, (x, y) in pos.items()}
    elif orientation == "LR":  # rotate CCW 90°
        pos = {n: (y, x) for n, (x, y) in pos.items()}
    elif orientation == "RL":  # rotate CW 90° + flip
        pos = {n: (-y, x) for n, (x, y) in pos.items()}

    return pos


def get_flow_cfg_path(flow_cfg_filename) -> str:
    """
    Get the absolute path to a flow configuration file.

    Args:
        flow_cfg_filename: Name of the YAML configuration file (e.g., "flow_27.yaml")

    Returns:
        str: Absolute path to the flow configuration file
    """
    return os.path.join(os.path.dirname(__file__), "flows", flow_cfg_filename)


def read_flow_cfg(flow_cfg_path) -> dict:
    """
    Read flow configuration from YAML file and check for duplicate keys at top level.

    Args:
        flow_cfg_path: Path to the YAML configuration file

    Returns:
        dict: Loaded YAML configuration

    Raises:
        ValueError: If duplicate keys are found at the top level
    """
    config_file = get_flow_cfg_path(flow_cfg_path)

    # Custom SafeLoader to detect duplicate keys
    class DuplicateKeyChecker(yaml.SafeLoader):
        def construct_mapping(self, node, deep=False):
            mapping = {}
            for key_node, value_node in node.value:
                key = self.construct_object(key_node, deep=deep)
                if key in mapping:
                    raise ValueError(
                        f"Duplicate key found in YAML file '{flow_cfg_path}': '{key}'"
                    )
                value = self.construct_object(value_node, deep=deep)
                mapping[key] = value
            return mapping

    with codecs.open(config_file, encoding="utf-8") as f:
        flow_cfg = yaml.load(f, Loader=DuplicateKeyChecker)
    return flow_cfg


def get_flow_module():
    """
    Get the flow module based on the CHAPTER_NUM environment variable.

    Returns:
        module: The flow module.

    Raises:
        SystemExit: If CHAPTER_NUM is not set or is not a valid integer,
                   or if the corresponding flow module does not exist.
    """
    # Get chapter number from environment variable
    CHAPTER_NUM = os.environ.get("chapter_num")
    if not CHAPTER_NUM:
        print("Error: CHAPTER_NUM environment variable is not set")
        sys.exit(1)

    try:
        CHAPTER_NUM = int(CHAPTER_NUM)
        CHAPTER_STR = f"{CHAPTER_NUM:02d}"
    except ValueError:
        print(f"Error: CHAPTER_NUM must be an integer, got: {CHAPTER_NUM}")
        sys.exit(1)

    # Try to import the specific flow module
    try:
        flow_module = importlib.import_module(f"DBHHelper.flows.flow_{CHAPTER_STR}")
        return flow_module
    except ImportError:
        print(
            f"Error: Chapter {CHAPTER_NUM} does not exist or flow module cannot be imported"
        )
        sys.exit(1)


def get_flow_info():
    """Get Flow class and chapter string at runtime to avoid import order issues

    Returns:
        tuple: (Flow class, CHAPTER_STR)
    """
    flow_module = get_flow_module()
    Flow = flow_module.Flow
    CHAPTER_STR = f"{Flow.chapter_number:02d}"
    return Flow, CHAPTER_STR


class GraphProcessor:
    def __init__(self):
        self.G = nx.DiGraph()
        self._merge_node = None

    def add_edge(self, op_type: InfixOpType, left: Callable, right: Callable):
        left_node_name = left.__name__
        right_node_name = right.__name__
        self.G.add_node(left_node_name, func=left)
        self.G.add_node(right_node_name, func=right)
        if op_type == InfixOpType.RIGHT:
            self._merge_node = None
            self.G.add_edge(left_node_name, right_node_name)
        elif op_type == InfixOpType.LEFT:
            self._merge_node = left
            self.G.add_edge(right_node_name, self._merge_node.__name__)
        elif op_type == InfixOpType.D_HEAD:
            self._merge_node = None
            # Not used in DBHFlow
            self.G.add_edge(left_node_name, right_node_name)
            self.G.add_edge(right_node_name, left_node_name)
        elif op_type == InfixOpType.D_TAIL:
            assert self._merge_node is not None
            self.G.add_edge(right_node_name, self._merge_node.__name__)
        return right


def generate_combined_id(combined_data: dict) -> str:
    """Generate a combined ID based on input dictionary using MD5 hash.

    Args:
        combined_data: Dictionary containing the data to hash

    Returns:
        str: hash_id is the 12-character MD5 hash
    """
    # Convert to consistent JSON string representation
    json_str = json.dumps(
        combined_data, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )

    # Generate MD5 hash and take first 12 characters for brevity
    hash_obj = hashlib.md5(json_str.encode("utf-8"))
    hash_id = hash_obj.hexdigest()[:12]

    return hash_id


class StatusAccessTracker:
    """Proxy class to track access to status keys."""

    def __init__(self, target_dict, access_callback):
        self._target = target_dict
        self._access_callback = access_callback

    def __getitem__(self, key):
        self._access_callback()
        return self._target[key]

    def __setitem__(self, key, value):
        self._access_callback()
        self._target[key] = value

    def __contains__(self, key):
        self._access_callback()
        return key in self._target

    def get(self, key, default=None):
        self._access_callback()
        return self._target.get(key, default)

    def keys(self):
        self._access_callback()
        return self._target.keys()

    def values(self):
        self._access_callback()
        return self._target.values()

    def items(self):
        self._access_callback()
        return self._target.items()

    def __iter__(self):
        self._access_callback()
        return iter(self._target)

    def __len__(self):
        self._access_callback()
        return len(self._target)

    def __repr__(self):
        return repr(self._target)

    def __str__(self):
        return str(self._target)


class FrozenKeysDict(dict):
    """Freeze key set at creation; allow value changes; disallow brand-new keys."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._allowed = frozenset(self.keys())

    def __setitem__(self, key, value):
        if key not in self._allowed:
            raise KeyError(
                f"New key not allowed: {key!r} (allowed: {sorted(self._allowed)})"
            )
        return super().__setitem__(key, value)

    def update(self, *args, **kwargs):
        new_items = dict(*args, **kwargs)
        extra = set(new_items) - self._allowed
        if extra:
            raise KeyError(f"New keys not allowed: {sorted(extra)}")
        return super().update(new_items)

    def setdefault(self, key, default=None):
        if key not in self._allowed:
            raise KeyError(f"New key not allowed: {key!r}")
        return super().setdefault(key, default)

    def __ior__(self, other):  # supports: d |= {...}
        self.update(other)
        return self
