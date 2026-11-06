#!/usr/bin/env python3
"""
DBH Choice Graph Visualizer
基于项目现有逻辑的choice_graph.json可视化工具
参考DBHHelper/utils.py中的draw_flowgraph函数和ABHBench/dcollect/collector.py中的图结构
"""

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Dict, Optional, Tuple

import networkx as nx
import plotly.graph_objects as go


class DBHChoiceGraphVisualizer:
    """基于DBH项目逻辑的Choice Graph可视化器"""

    def __init__(self, json_file_path: str):
        self.json_file_path = json_file_path
        self.graph: Optional[nx.DiGraph] = None
        self.raw_data: Optional[dict] = None

    def load_choice_graph(self) -> bool:
        """
        加载choice_graph.json文件
        使用与项目相同的加载方式：nx.node_link_graph
        """
        print(f"\n=== Loading Choice Graph from {self.json_file_path} ===")

        try:
            with open(self.json_file_path, "r", encoding="utf-8") as f:
                self.raw_data = json.load(f)

            if not self.raw_data:
                print("Error: choice_graph.json is empty")
                return False

            # 使用NetworkX的node_link_graph加载（与项目逻辑一致）
            self.graph = nx.node_link_graph(self.raw_data, directed=True)

            print("✓ Successfully loaded choice graph")
            print(f"  Nodes: {self.graph.number_of_nodes()}")
            print(f"  Edges: {self.graph.number_of_edges()}")

            # 检查root节点
            if "root" not in self.graph:
                print("⚠ Warning: No root node found in graph")
            else:
                print("✓ Root node found")

            return True

        except FileNotFoundError:
            print(f"Error: File {self.json_file_path} not found")
            return False
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON format - {e}")
            return False
        except Exception as e:
            print(f"Error loading choice graph: {e}")
            return False

    def analyze_graph_structure(self):
        """分析图结构，显示与项目逻辑相关的信息"""
        if not self.graph:
            print("No graph loaded")
            return

        print("\n=== Graph Structure Analysis ===")
        print(f"Graph type: {type(self.graph)}")
        print(f"Is directed: {self.graph.is_directed()}")
        print(f"Number of nodes: {self.graph.number_of_nodes()}")
        print(f"Number of edges: {self.graph.number_of_edges()}")

        # 分析节点属性（基于项目中的节点结构）
        print("\n--- Node Analysis ---")
        choice_nodes = 0

        for node_id in self.graph.nodes():
            node_data = self.graph.nodes[node_id]

            if node_id == "root":
                print(f"Root node: {node_id}")
                choice_to_child = node_data.get("choice_to_child", {})
                print(f"  Root choices: {len(choice_to_child)}")
                if choice_to_child:
                    for choice, child in list(choice_to_child.items())[:3]:
                        print(f"    '{choice}' -> {child}")
                    if len(choice_to_child) > 3:
                        print(f"    ... and {len(choice_to_child) - 3} more")
            else:
                choice_nodes += 1
                # 分析选择节点的属性
                available_choices = node_data.get("available_choices", {})
                explored_choices = node_data.get("explored_choices", [])
                unexplored_choices = node_data.get("unexplored_choices", [])

                if choice_nodes <= 5:  # 只显示前5个节点的详细信息
                    print(f"Choice node: {node_id}")
                    print(
                        f"  Available: {len(available_choices)}, Explored: {len(explored_choices)}, Unexplored: {len(unexplored_choices)}"
                    )

        if choice_nodes > 5:
            print(f"... and {choice_nodes - 5} more choice nodes")

        # 计算探索统计（与项目逻辑一致）
        explored_count, total_count = self._get_exploration_stats()
        if total_count > 0:
            completion_rate = explored_count / total_count * 100
            print(
                f"\nExploration Progress: {explored_count}/{total_count} ({completion_rate:.1f}%)"
            )

        # 分析未完成节点前缀
        self.top_10_incomplete_prefixes = self._analyze_incomplete_node_prefixes()

        # 图的连通性分析
        print("\nGraph Properties:")
        print(
            f"  Is connected (undirected): {nx.is_connected(self.graph.to_undirected())}"
        )
        print(f"  Is DAG: {nx.is_directed_acyclic_graph(self.graph)}")

        if self.graph.number_of_nodes() > 0:
            try:
                print(f"  Average clustering: {nx.average_clustering(self.graph):.3f}")
            except Exception:
                print("  Average clustering: N/A")

    def _get_exploration_stats(self) -> Tuple[int, int]:
        """
        计算探索统计，与ABHBench/dcollect/collector.py中的逻辑一致
        """
        if not self.graph:
            return 0, 0

        explored_count = 0
        total_count = 0

        # 遍历所有非root节点
        for node_id in self.graph.nodes():
            if node_id == "root":
                continue

            node_data = self.graph.nodes[node_id]

            # 计算总的可用选择数
            available_choices = node_data.get("available_choices", {})
            total_count += len(available_choices)

            # 计算已探索的选择数
            explored_choices = node_data.get("explored_choices", [])
            explored_count += len(explored_choices)

        return explored_count, total_count

    def _analyze_incomplete_node_prefixes(self):
        """
        分析未完成节点的前缀统计，按前缀合并（不考虑hash）
        返回前10个前缀列表，用于可视化颜色分配
        """
        if not self.graph:
            return []

        print("\n--- Incomplete Node Prefix Analysis ---")

        # 收集所有未完成的节点及其未探索选择数量
        incomplete_nodes = []
        prefix_data = {}  # {prefix: {'nodes': count, 'unexplored': total_unexplored}}

        # 计算总的探索统计
        total_explored, total_choices = self._get_exploration_stats()
        total_unexplored = total_choices - total_explored

        for node_id in self.graph.nodes():
            if node_id == "root":
                continue

            node_data = self.graph.nodes[node_id]
            unexplored_choices = node_data.get("unexplored_choices", [])

            # 如果有未探索的选择，则认为是未完成的节点
            if len(unexplored_choices) > 0:
                incomplete_nodes.append(node_id)

                # 提取前缀（去掉最后的hash部分）
                if "_" in node_id:
                    prefix = "_".join(node_id.split("_")[:-1])
                else:
                    prefix = node_id  # 如果没有下划线，整个ID就是前缀

                # 统计前缀数据
                if prefix not in prefix_data:
                    prefix_data[prefix] = {"nodes": 0, "unexplored": 0}

                prefix_data[prefix]["nodes"] += 1
                prefix_data[prefix]["unexplored"] += len(unexplored_choices)

        total_incomplete = len(incomplete_nodes)

        print(f"Total incomplete nodes: {total_incomplete}")
        print(f"Total unexplored choices: {total_unexplored}")

        # 按节点数量排序获取前10个前缀
        sorted_prefixes = sorted(
            prefix_data.items(), key=lambda x: x[1]["nodes"], reverse=True
        )
        top_10_prefixes = [prefix for prefix, _ in sorted_prefixes[:10]]

        if total_incomplete > 0:
            print(f"Unique prefixes: {len(prefix_data)}")

            # 第一份排序：按节点数量排序
            print("\nTop 20 incomplete node prefixes (sorted by node count):")
            for i, (prefix, data) in enumerate(sorted_prefixes[:20], 1):
                node_count = data["nodes"]
                unexplored_count = data["unexplored"]
                node_percentage = (node_count / total_incomplete) * 100
                unexplored_percentage = (
                    (unexplored_count / total_unexplored) * 100
                    if total_unexplored > 0
                    else 0
                )

                # 前10个用特殊标记表示会在图中用不同颜色显示
                marker = " *" if i <= 10 else ""
                print(
                    f"  {i:2d}. {prefix}: {node_count} nodes ({node_percentage:.1f}%), {unexplored_count} unexplored ({unexplored_percentage:.1f}%){marker}"
                )

            if len(prefix_data) > 20:
                remaining = len(prefix_data) - 20
                print(f"  ... and {remaining} more prefixes")

            # 第二份排序：按未探索选择数量排序
            sorted_by_unexplored = sorted(
                prefix_data.items(), key=lambda x: x[1]["unexplored"], reverse=True
            )
            print("\nTop 20 incomplete node prefixes (sorted by unexplored choices):")
            for i, (prefix, data) in enumerate(sorted_by_unexplored[:20], 1):
                node_count = data["nodes"]
                unexplored_count = data["unexplored"]
                node_percentage = (node_count / total_incomplete) * 100
                unexplored_percentage = (
                    (unexplored_count / total_unexplored) * 100
                    if total_unexplored > 0
                    else 0
                )

                print(
                    f"  {i:2d}. {prefix}: {node_count} nodes ({node_percentage:.1f}%), {unexplored_count} unexplored ({unexplored_percentage:.1f}%)"
                )

            if len(prefix_data) > 20:
                remaining = len(prefix_data) - 20
                print(f"  ... and {remaining} more prefixes")

            print(
                "\n  * Top 10 prefixes (by node count) will be shown in distinct colors in the visualization"
            )
            print(
                f"  * Unexplored percentages are relative to total unexplored choices ({total_unexplored})"
            )
        else:
            print("No incomplete nodes found - all nodes are fully explored!")

        return top_10_prefixes

    def create_plotly_visualization(
        self,
        output_file: str = "choice_graph_plotly.html",
        image_file: str = "choice_graph_plotly.png",
    ):
        """
        使用Plotly创建交互式可视化，参考DBHHelper/utils.py中的draw_flowgraph函数

        Args:
            output_file: HTML输出文件名
            image_file: 高分辨率图片输出文件名
        """
        if not self.graph:
            print("No graph loaded")
            return

        print("\n=== Creating Plotly Visualization ===")

        # 使用简化的层次化布局
        try:
            pos = self._simple_hierarchical_layout(self.graph)
            layout_type = "Hierarchical layout (using node level field)"
        except Exception as e:
            print(f"Layout failed: {e}, using spring layout as fallback")
            pos = nx.spring_layout(self.graph, k=2, iterations=50)
            layout_type = "Spring layout (fallback)"

        print(f"Using {layout_type}")

        # 定义12种颜色方案 - 使用高对比度、易区分的颜色，避免与黄色和root节点的lightgreen接近
        # 前10种颜色用于前10个未完成节点前缀
        top_10_colors = [
            "#FF0000",  # 纯红色
            "#0000FF",  # 纯蓝色 (将绿色移除，避免与root节点混淆)
            "#FF00FF",  # 品红色
            "#00FFFF",  # 青色
            "#FF8000",  # 橙色
            "#8000FF",  # 紫色
            "#FF0080",  # 玫红色
            "#800000",  # 深红色 (替换深绿色)
            "#000080",  # 深蓝色 (替换深绿色)
            "#800080",  # 深紫色
        ]

        # 获取前10个未完成节点前缀，如果还没有分析过则先分析
        if not hasattr(self, "top_10_incomplete_prefixes"):
            self.top_10_incomplete_prefixes = self._analyze_incomplete_node_prefixes()
        top_10_prefixes = self.top_10_incomplete_prefixes

        # 创建前缀到颜色的映射
        prefix_color_map = {}
        for i, prefix in enumerate(top_10_prefixes[:10]):
            prefix_color_map[prefix] = top_10_colors[i]

        # 创建边的轨迹
        edge_trace = go.Scatter(
            x=[],
            y=[],
            line=dict(width=1, color="darkgray"),
            hoverinfo="none",
            mode="lines",
            name="Edges",
        )

        # 添加边到轨迹
        for edge in self.graph.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_trace["x"] += (x0, x1, None)
            edge_trace["y"] += (y0, y1, None)

        # 准备节点数据
        node_x = []
        node_y = []
        node_text = []
        node_colors = []
        node_info = []

        for node in self.graph.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)

            node_data = self.graph.nodes[node]

            if node == "root":
                node_text.append("ROOT")
                node_colors.append("lightgreen")
                choice_to_child = node_data.get("choice_to_child", {})
                node_info.append(f"Root Node<br>Choices: {len(choice_to_child)}")
            else:
                # 显示完整的节点ID
                node_text.append(node)

                # 根据新的12色方案着色
                available_choices = node_data.get("available_choices", {})
                explored_choices = node_data.get("explored_choices", [])
                unexplored_choices = node_data.get("unexplored_choices", [])

                # 提取节点前缀
                if "_" in node:
                    node_prefix = "_".join(node.split("_")[:-1])
                else:
                    node_prefix = node

                if len(unexplored_choices) == 0 and len(explored_choices) > 0:
                    # 已完成节点 - 使用灰蓝色
                    node_colors.append("#B0C4DE")  # 浅钢蓝色
                elif len(unexplored_choices) > 0:
                    # 未完成节点 - 检查是否在前10个前缀中
                    if node_prefix in prefix_color_map:
                        # 前10个未完成节点前缀 - 使用对应的特殊颜色
                        node_colors.append(prefix_color_map[node_prefix])
                    else:
                        # 其他未完成节点（未探索的未进排序节点）- 使用黄色
                        node_colors.append("#FFFF00")  # 纯黄色
                else:
                    # 未探索节点 - 使用浅灰色
                    node_colors.append("#D3D3D3")  # 浅灰色

                node_info.append(
                    f"Node: {node}<br>"
                    f"Available: {len(available_choices)}<br>"
                    f"Explored: {len(explored_choices)}<br>"
                    f"Unexplored: {len(unexplored_choices)}"
                )

        # 创建节点轨迹
        node_trace = go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            hoverinfo="text",
            text=node_text,
            textposition="middle center",
            hovertext=node_info,
            marker=dict(showscale=False, color=node_colors, size=30, line_width=2),
            name="Nodes",
        )

        # 根据节点数量动态调整图形尺寸和参数
        node_count = self.graph.number_of_nodes()

        # 针对大量节点优化图形尺寸，增加宽度和高度以适应完整ID显示
        if node_count > 3000:
            width, height = 12000, 9000  # 超大图，更宽更高
            node_size = 15
            font_size = 8
        elif node_count > 1000:
            width, height = 9000, 6750  # 大图，更宽更高
            node_size = 20
            font_size = 10
        elif node_count > 500:
            width, height = 6000, 4500  # 中图，更宽更高
            node_size = 25
            font_size = 12
        else:
            width, height = 3600, 2700  # 小图，更宽更高
            node_size = 30
            font_size = 14

        # 更新节点轨迹的大小
        node_trace.update(
            marker=dict(
                showscale=False, color=node_colors, size=node_size, line_width=2
            )
        )

        # 创建图形
        fig = go.Figure(
            data=[edge_trace, node_trace],
            layout=go.Layout(
                title=dict(
                    text="DBH Choice Graph Visualization",
                    font=dict(size=max(16, font_size + 2)),
                ),
                showlegend=True,
                hovermode="closest",
                width=width,
                height=height,
                margin=dict(b=60, l=20, r=20, t=80),
                annotations=[
                    dict(
                        text="Node Colors: Green=Root, Steel Blue=Completed, Yellow=Other Incomplete, 10 Colors=Top 10 Incomplete Prefixes",
                        showarrow=False,
                        xref="paper",
                        yref="paper",
                        x=0.005,
                        y=-0.002,
                        xanchor="left",
                        yanchor="bottom",
                        font=dict(size=max(10, font_size - 2)),
                    )
                ],
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                plot_bgcolor="white",
            ),
        )

        # 保存HTML文件
        fig.write_html(output_file)
        print(f"✓ Interactive visualization saved to: {output_file}")

        # 保存高分辨率图片
        if image_file:
            try:
                # 使用更高的分辨率和质量设置
                fig.write_image(
                    image_file,
                    width=width,
                    height=height,
                    scale=2,  # 2倍缩放提高分辨率
                    format="png",
                )
                print(f"✓ High-resolution image saved to: {image_file}")
            except Exception as e:
                print(f"⚠ Warning: Could not save image file - {e}")
                print(
                    "  Note: Image export requires 'kaleido' package: pip install kaleido"
                )
        else:
            print("✓ Image export skipped (--no-image flag used)")

        return fig

    def _simple_hierarchical_layout(self, G: nx.DiGraph) -> Dict:
        """
        简化的层次化布局 - 使用节点中的level字段作为深度
        Root节点在最左侧，子节点向右扩展
        """
        # 获取每个节点的层级（使用节点中的level字段）
        levels = {}
        for node in G.nodes():
            node_data = G.nodes[node]
            if node == "root":
                levels[node] = 0  # Root节点层级为0
            else:
                # 使用节点数据中的level字段，如果没有则默认为0
                levels[node] = node_data.get("level", 0)

        # 按层级分组节点
        level_nodes = {}
        for node, level in levels.items():
            if level not in level_nodes:
                level_nodes[level] = []
            level_nodes[level].append(node)

        # 为每个层级的节点分配位置
        pos = {}

        for level, nodes in level_nodes.items():
            node_count = len(nodes)

            # 对节点按名称排序，确保每次生成的图都有固定的排序
            sorted_nodes = sorted(nodes)

            # 所有层级的节点都按照相同的逻辑排列
            if node_count == 1:
                # 单个节点居中
                pos[sorted_nodes[0]] = (level * 3, 0)  # 水平间距为3
            else:
                # 多个节点垂直分布
                y_spacing = 2.0  # 垂直间距
                start_y = -(node_count - 1) * y_spacing / 2

                for i, node in enumerate(sorted_nodes):
                    x = level * 3  # 水平位置基于层级
                    y = start_y + i * y_spacing
                    pos[node] = (x, y)

        return pos

    def export_graph_data(self, output_file: str = "choice_graph_data.json"):
        """导出图数据用于进一步分析"""
        if not self.graph:
            print("No graph loaded")
            return

        print("\n=== Exporting Graph Data ===")

        # 准备导出数据
        export_data = {
            "graph_info": {
                "nodes": self.graph.number_of_nodes(),
                "edges": self.graph.number_of_edges(),
                "is_dag": nx.is_directed_acyclic_graph(self.graph),
                "is_connected": nx.is_connected(self.graph.to_undirected()),
            },
            "exploration_stats": {
                "explored_count": self._get_exploration_stats()[0],
                "total_count": self._get_exploration_stats()[1],
                "completion_rate": self._get_exploration_stats()[0]
                / max(1, self._get_exploration_stats()[1])
                * 100,
            },
            "nodes": [],
            "edges": [],
        }

        # 导出节点数据
        for node_id in self.graph.nodes():
            node_data = self.graph.nodes[node_id]
            node_info = {
                "id": node_id,
                "type": "root" if node_id == "root" else "choice",
                "available_choices": len(node_data.get("available_choices", {})),
                "explored_choices": len(node_data.get("explored_choices", [])),
                "unexplored_choices": len(node_data.get("unexplored_choices", [])),
                "choice_to_child": node_data.get("choice_to_child", {}),
            }
            export_data["nodes"].append(node_info)

        # 导出边数据
        for edge in self.graph.edges():
            edge_data = self.graph.edges[edge]
            edge_info = {
                "source": edge[0],
                "target": edge[1],
                "choice_text": edge_data.get("choice_text", ""),
            }
            export_data["edges"].append(edge_info)

        # 保存到文件
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        print(f"✓ Graph data exported to: {output_file}")
        return export_data


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="DBH Choice Graph Visualizer - 基于项目逻辑的可视化工具"
    )
    parser.add_argument(
        "json_file",
        nargs="?",
        default="choice_graph.json",
        help="Path to the choice graph JSON file",
    )
    parser.add_argument(
        "--plotly-output",
        default="choice_graph_plotly.html",
        help="Output file for Plotly HTML visualization",
    )
    parser.add_argument(
        "--image-output",
        default="choice_graph_plotly.png",
        help="Output file for high-resolution image",
    )
    parser.add_argument(
        "--export-data",
        default="choice_graph_data.json",
        help="Output file for exported graph data",
    )
    parser.add_argument(
        "--no-plotly", action="store_true", help="Skip Plotly visualization"
    )
    parser.add_argument("--no-image", action="store_true", help="Skip image export")
    parser.add_argument(
        "--analysis-only",
        action="store_true",
        help="Only perform analysis, no visualization",
    )

    args = parser.parse_args()

    # 创建可视化器
    visualizer = DBHChoiceGraphVisualizer(args.json_file)

    # 加载数据
    if not visualizer.load_choice_graph():
        return 1

    # 分析结构
    visualizer.analyze_graph_structure()

    if not args.analysis_only:
        # 创建可视化
        if not args.no_plotly:
            image_file = None if args.no_image else args.image_output
            visualizer.create_plotly_visualization(args.plotly_output, image_file)

        # 导出数据
        visualizer.export_graph_data(args.export_data)

    print("\n=== Visualization Complete ===")
    return 0


if __name__ == "__main__":
    exit(main())
