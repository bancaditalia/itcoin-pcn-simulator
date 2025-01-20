import csv
import itertools
import json
import logging
import pathlib
import sys

import matplotlib as mpl
import matplotlib.colors as mcolors
import metis
import networkx as nx

from plasma_network_generator.core import NodeType
from plasma_network_generator.utils import configure_logging


########################################################################################################################
#                                                Main partitioner driver                                                 #
########################################################################################################################
def parse_commandline_args(argv):
    # These are the defaults in place when no commandline flag is passed
    cmdline_flags = {
        "input_file": "output.graphml",
        "output_dir": f"{pathlib.Path.cwd()}",  # CLoTH output files are saved to cwd by default
        "n_partitions": 1,  # One partition only by default
    }

    if len(argv) > 1:
        args = argv[1:]
        while len(args) > 0:
            arg = args.pop(0)
            if arg[:1] == "-":
                try:
                    cmdline_flags.update(
                        {
                            "-input": lambda: {"input_file": args.pop(0)},
                            "-dir": lambda: {"output_dir": args.pop(0)},
                            "-k": lambda: {"n_partitions": args.pop(0)},
                        }[arg](),
                    )
                except KeyError:
                    print(f'Unknown commandline flag: "{arg}"')
                    exit(-1)
            else:
                print(f'Unknown commandline flag: "{arg}"')
                exit(-1)

    return cmdline_flags


def cloth_output(
    plasma_network: nx.MultiDiGraph, output_dir: pathlib.Path, n_partitions: int
) -> None:
    g = nx.DiGraph(plasma_network)
    g.graph["edge_weight_attr"] = "weight"
    g.graph["node_weight_attr"] = "weight"

    ufactors = {2: 50, 4: 800, 8: 50, 16: 50}
    if n_partitions > 1:
        (edgecuts, parts) = metis.part_graph(
            g, n_partitions, objtype="cut", ufactor=ufactors[n_partitions]
        )
    else:
        parts = [0] * len(g.nodes)
    colors = mpl.colormaps["Set1"]
    colors = [mcolors.to_hex(color) for color in colors(range(n_partitions))]
    counter = {k: {} for k in range(n_partitions)}
    for i, p in enumerate(parts):
        g.nodes[i]["color"] = colors[p]
        g.nodes[i]["partition"] = p
        if g.nodes[i]["type"] not in counter[p]:
            counter[p][g.nodes[i]["type"]] = 0
        counter[p][g.nodes[i]["type"]] += 1

    logging.info("%s", json.dumps(counter, indent=4))

    with (output_dir / "plasma_network_nodes.csv").open(mode="w") as node_file:
        node_writer = csv.writer(node_file)
        node_writer.writerow(["id", "label", "country", "partition", "intermediary"])
        for key, node in g.nodes(data=True):
            intermediary = node.get("intermediary", "")
            node_writer.writerow(
                [key, node["label"], node["country"], node["partition"], intermediary],
            )

    with (
        (output_dir / "plasma_network_edges.csv").open(mode="w") as edge_file,
        (output_dir / "plasma_network_channels.csv").open(mode="w") as channel_file,
    ):
        channel_writer = csv.writer(channel_file)
        channel_writer.writerow(
            [
                "id",
                "edge1_id",
                "edge2_id",
                "node1_id",
                "node2_id",
                "capacity",
                "is_private",
            ],
        )

        edge_writer = csv.writer(edge_file)
        edge_writer.writerow(
            [
                "id",
                "channel_id",
                "counter_edge_id",
                "from_node_id",
                "to_node_id",
                "balance",
                "fee_base",
                "fee_proportional",
                "min_htlc",
                "timelock",
            ],
        )

        channel_id = 0
        edge_id = 0

        edges = sorted(
            plasma_network.edges(keys=True, data=True),
            key=lambda x: x[2],
        )
        for key, values in itertools.groupby(edges, key=lambda x: x[2]):
            dir1 = str(edge_id)
            dir2 = str(edge_id + 1)
            values = list(values)
            edge1 = values[0]
            edge_row1 = [
                dir1,
                str(channel_id),
                dir2,
                edge1[0],
                edge1[1],
                str(int(edge1[3]["balance"])),
                "0",
                "0",
                "1",
                "10",
            ]
            edge_writer.writerow(edge_row1)
            edge2 = values[1]
            edge_row2 = [
                dir2,
                str(channel_id),
                dir1,
                edge2[0],
                edge2[1],
                str(int(edge2[3]["balance"])),
                "0",
                "0",
                "1",
                "10",
            ]
            edge_writer.writerow(edge_row2)

            plasma_network[edge1[0]][edge1[1]][key]["cloth_edge_id"] = dir1
            plasma_network[edge2[0]][edge2[1]][key]["cloth_edge_id"] = dir2

            total_capacity = int(edge1[3]["balance"] + edge2[3]["balance"])
            assert (
                total_capacity == int(edge1[3]["capacity"]) == int(edge2[3]["capacity"])
            )
            is_private = int(edge1[3]["is_private"])
            channel_row = [
                str(channel_id),
                dir1,
                dir2,
                edge1[0],
                edge1[1],
                str(total_capacity),
                str(is_private),
            ]
            channel_writer.writerow(channel_row)
            channel_id += 1
            edge_id += 2

    all_intermediaries = [
        key
        for key, node in plasma_network.nodes(data=True)
        if node["type"] == NodeType.INTERMEDIARY.value
    ]
    with (output_dir / "plasma_paths.csv").open(mode="w") as path_file:
        path_writer = csv.writer(path_file)
        path_writer.writerow(["src", "target", "path"])
        for i1 in all_intermediaries:
            for i2 in all_intermediaries:
                if i1 != i2:
                    try:
                        path = nx.shortest_path(plasma_network, i1, i2)
                        edges = nx.utils.pairwise(path)
                        route = [
                            plasma_network[u][v][list(plasma_network[u][v].keys())[0]][
                                "cloth_edge_id"
                            ]
                            for u, v in edges
                        ]
                        if len(route) == 1:
                            formatted_route = "[" + route[0] + "]"
                        else:
                            formatted_route = "[" + ",".join(route) + "]"
                        path_writer.writerow([i1, i2, formatted_route])
                    except nx.NetworkXNoPath:
                        logging.warning(
                            "No path among %s and %s",
                            plasma_network.nodes[i1]["label"],
                            plasma_network.nodes[i2]["label"],
                        )


def plasma_network_generator_cloth_dump_main(argv) -> int:
    cmdline_flags = parse_commandline_args(argv)
    configure_logging(True)
    output_dir = pathlib.Path(cmdline_flags["output_dir"]).resolve()
    if not output_dir.is_dir():
        print(
            f"ERROR: {output_dir} does not exist or is not a directory. Please create it",
        )
        return 1
    plasma_network = nx.read_graphml(
        cmdline_flags["input_file"],
        node_type=int,
        edge_key_type=str,
        force_multigraph=True,
    )
    cloth_output(
        plasma_network,
        cmdline_flags["output_dir"],
        int(cmdline_flags["n_partitions"]),
    )
    return 0


if __name__ == "__main__":
    sys.exit(plasma_network_generator_cloth_dump_main(sys.argv))
