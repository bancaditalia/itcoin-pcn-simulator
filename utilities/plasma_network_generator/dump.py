import pathlib

import networkx as nx

from plasma_network_generator.utils import (
    try_is_weakly_connected,
)

########################################################################################################################
#                     Dumping the network(s) plus possibly some network information (verbose mode)                     #
########################################################################################################################


def dump_info_about_layeers_and_nodes(layer_nodes, rnd_model_params):
    print("***** PAYMENT LAYERS AND NODES *****")
    print(
        f"There are {rnd_model_params['number_of_nodes_in_simulation']} nodes overall, organized into {len(layer_nodes)} layers:"
    )
    for layer_id in layer_nodes:
        print(
            "\t- {}: {} {}s, labelled {}".format(
                layer_id,
                layer_nodes[layer_id]["count"],
                layer_nodes[layer_id]["type"],
                layer_nodes[layer_id]["label"].format(nation="<Nation>", id="<IDX>"),
            ),
        )
    print("Ratios among layer sizes:")
    print(
        f"\t- 1 CB every {rnd_model_params['intermediary_to_CB_ratio']} intermediaries"
    )
    print(
        f"\t- 1 intermediary every {rnd_model_params['citizens_to_intermediary_ratio']:.2f} retail users"
    )
    print(f"\t- 1 CB every {rnd_model_params['citizens_to_CB_ratio']:.2f} retail users")
    print(
        f"\t- 1 merchant every {1 / rnd_model_params['merchants_to_retail_users_ratio']:.2f} retail users"
    )


def dump_info_about_network_random_models(subnetworks_models):
    print("***** RANDOM PAYMENT NETWORK MODELS *****")
    print(
        f"The plasma network is built by composing {len(subnetworks_models)} random subnetworks:",
    )
    for subnetwork in subnetworks_models:
        print(f"\t- {subnetwork['description']}")
        print(f"\t\t- model: {subnetwork['network_model'][0].__name__}")
        print(f"\t\t- parameters: {subnetwork['network_model'][1]}")
        node_sets = subnetwork["network_nodes"]
        node_sets_desc = [
            f"{node_set['type']}s ({node_set['count']})" for node_set in node_sets
        ]
        print(f"\t\t- over nodes: {' + '.join(node_sets_desc)}")


def dump_info_about_auxiliary_network_random_models(subnetworks_models):
    print("***** RANDOM AUXILIARY NETWORK MODELS *****")
    print("The following auxiliary (non-payment) networks are included:")
    for subnetwork in subnetworks_models:
        print(f"\t- {subnetwork['description']}")
        print(f"\t\t- model: {subnetwork['network_model'][0].__name__}")
        node_sets = subnetwork["network_nodes"]
        node_sets_desc = [
            f"{node_set['type']}s ({node_set['count']})" for node_set in node_sets
        ]
        print(f"\t\t- over nodes: {' + '.join(node_sets_desc)}")


def dump_network_analysis(plasma_network, subnetwork_instances):
    def _dump_network_analysis(subnetwork):
        print(f"\t-Number of channels: {subnetwork.number_of_edges()}")
        print(
            f"\t-Average channels per node: "
            f"{float(subnetwork.number_of_edges()) / subnetwork.number_of_nodes() if subnetwork.number_of_nodes() > 0 else float('nan')}"
        )
        is_weakly_connected = try_is_weakly_connected(subnetwork)
        print(
            "\t-Is connected (i.e., not made of disjoint components): {}".format(
                (
                    "YES"
                    if is_weakly_connected
                    else "NO" if is_weakly_connected is not None else "UNKNOWN"
                ),
            ),
        )
        is_strongly_connected = try_is_weakly_connected(subnetwork)
        print(
            "\t-Is strongly connected (i.e., can follow channels from every node to every other node): {}".format(
                (
                    "YES"
                    if is_strongly_connected
                    else "NO" if is_weakly_connected is not None else "UNKNOWN"
                ),
            ),
        )
        if is_strongly_connected is False:
            print(
                f"\t-Number of strongly connected components: {nx.number_strongly_connected_components(subnetwork)}",
            )
        elif is_strongly_connected is True:
            print(
                f"\t-Diameter (max number of hops): {nx.algorithms.distance_measures.diameter(subnetwork)}",
            )

    print("***** PAYMENT NETWORK INSTANCES ANALYSIS *****")
    for subnetwork in subnetwork_instances:
        print(f"Subnetwork: {subnetwork.name}")
        _dump_network_analysis(subnetwork)

    print(plasma_network.graph["description"] + ":")
    _dump_network_analysis(plasma_network)


# Dumping the plasma network (and possibly its subnetworks individually) to file or stdout
def dump_plasma_network(plasma_network, subnetwork_instances, cmdline_flags):
    def output_file_for_subnetwork(subnetwork_name):
        network_file_name = cmdline_flags["output_file"]
        output_dir = pathlib.Path(cmdline_flags["output_dir"])
        subnetwork_file_name = (
            network_file_name.name.split(".")[0]
            + "."
            + subnetwork_name
            + "."
            + network_file_name.name.split(".")[1]
        )
        return (output_dir / subnetwork_file_name).open(mode="wb")

    if cmdline_flags["dump_network"]:
        cmdline_flags["output_formatter"](
            plasma_network,
            str(
                pathlib.Path(cmdline_flags["output_dir"]) / cmdline_flags["output_file"]
            ),
        )

    if cmdline_flags["dump_subnetworks"]:
        for subnetwork_instance in subnetwork_instances:
            cmdline_flags["output_formatter"](
                subnetwork_instance,
                output_file_for_subnetwork(
                    subnetwork_instance.graph["Nation"]
                    + "-"
                    + subnetwork_instance.graph["ID"],
                ),
            )
