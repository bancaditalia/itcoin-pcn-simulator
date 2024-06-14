"""Plasma Network Generation Procedures."""

from collections import defaultdict
from functools import reduce

import networkx as nx

from plasma_network_generator.core import ChannelType, NationSpecs, NodeType
from plasma_network_generator.utils import (
    EU_COUNTRY_CODE,
    eu,
    float_round,
    import_networkx_type,
)


def generate_plasma_network(
    payment_subnetworks_random_models,
    rnd_seed,
    nations: NationSpecs,
    unique_cb: bool = False,
):
    # The different subnetworks are generated one by one, according to the rnd_model_params in their random model
    # (we reify the list and do nt allow "map" to work lazily here with the subsequent "reduce" because we need to
    # individually return the subnetwork instances for possibly dumping them to file)

    subnetwork_instances = []

    # national models
    # sorted for reproducibility
    nations_list = sorted(nations.nations)
    for nation in nations_list:
        subnetwork_instances.extend(
            [
                instantiate_plasma_subnetwork(
                    rnd_model,
                    rnd_seed,
                    [nation],
                    unique_cb=unique_cb,
                )
                for rnd_model in payment_subnetworks_random_models
                if rnd_model["type"] == ChannelType.NATIONAL.value
            ],
        )
    # international models
    subnetwork_instances.extend(
        [
            instantiate_plasma_subnetwork(
                rnd_model,
                rnd_seed,
                nations_list,
                unique_cb=unique_cb,
            )
            for rnd_model in payment_subnetworks_random_models
            if rnd_model["type"] == ChannelType.INTERNATIONAL.value
        ],
    )

    # The subnetworks are merged into the full plasma network; the core funtion here is nx.compose,
    # which takes 2 graphs and combines them by cumulating all nodes and arcs from both graphs.
    # The "key" used to identify nodes in the join is their "label", so the idea for a proper combination is to
    # name nodes consistently in different subnetworks even when looked at separately, which we do.
    plasma_network = reduce(nx.compose, subnetwork_instances)
    plasma_network = nx.convert_node_labels_to_integers(
        plasma_network,
        label_attribute="label",
    )
    # clean up global network attributes
    plasma_network.graph.pop("ID", None)
    plasma_network.graph.pop("Nation", None)
    for src, target, _key in plasma_network.edges:
        if (
            plasma_network.nodes[src]["type"] == NodeType.INTERMEDIARY.value
            and "intermediary" in plasma_network.nodes[target]
        ):
            plasma_network.nodes[target]["intermediary"] = src

    return (plasma_network, subnetwork_instances)


def _set_balances(g, g_incoming, subnetwork) -> None:
    """Set the balances of a plasma (sub)network, both for the forward and backward edges.

    The function does side-effect on the edge attributes of both g and g_incoming.

    This function assumes that the capacity edge attribute has been set both for the forward and backward directions of
     the same channel.

    If subnetwork['network_bidir'] is True, then the balance is set to half the capacity for both the forward and
     backward edge; however, if the channel is between an user and an intermediary, then 10% of the capacity is set on
     the user side and the rest on the intermediary side.

    If subnetwork['network_bidir'] is False, then the balance is set to the capacity for the forward edge and to 0 for
     the backward edge.

    Args:
    ----
        g: the plasma network, forward edges
        g_incoming: the plasma network, backward edges
        subnetwork: the capacity network configuration
    """
    for edge in g.edges:
        (start, end, name) = edge
        reverse_edge = (end, start, name)
        channel_capacity = int(g.edges[edge]["capacity"])
        assert (
            channel_capacity == g_incoming.edges[reverse_edge]["capacity"]
        ), f'{channel_capacity} != {g_incoming.edges[reverse_edge]["capacity"]}'
        g.edges[edge]["capacity"] = int(g.edges[edge]["capacity"])
        g_incoming.edges[reverse_edge]["capacity"] = int(
            g_incoming.edges[reverse_edge]["capacity"]
        )
        if subnetwork["network_bidir"]:
            # if the network is bidirectional, we set the balance to half the capacity for both the forward and backward
            start_nt = NodeType(g.nodes[start]["type"])
            end_nt = NodeType(g.nodes[end]["type"])
            # 10% on user side, the rest on intermediary side
            if start_nt == NodeType.INTERMEDIARY and end_nt.is_retail():
                balance = channel_capacity * 0.9
            elif start_nt.is_retail() and end_nt == NodeType.INTERMEDIARY:
                balance = channel_capacity * 0.1
            else:
                balance = channel_capacity / 2
        else:
            # if the network is not bidirectional, we set the balance to the capacity for the forward edge and to 0 for
            # the backward edge
            balance = channel_capacity

        # set the balances
        g.edges[edge]["balance"] = int(balance)
        g_incoming.edges[reverse_edge]["balance"] = int(channel_capacity - balance)


def instantiate_plasma_subnetwork(
    subnetwork,
    rnd_seed,
    nations: list[str],
    unique_cb: bool = False,
):
    # We instantiate an (empty) graph of the proper type for this intra-layer or inter-layer level
    if len(nations) == 0:
        msg = "the nations list is empty, at least one nation is required"
        raise ValueError(msg)

    is_international_network = subnetwork["type"] == ChannelType.INTERNATIONAL.value

    network_cls = import_networkx_type(subnetwork["network_type"])
    if is_international_network:
        nation_id = "-".join(sorted(nations)) if unique_cb else EU_COUNTRY_CODE
    else:
        nation_id = nations[0]

    g = network_cls(
        ID=subnetwork["ID"],
        Nation=nation_id,
        description=subnetwork["description"],
    )

    # We generate the nodes and attach the proper attributes and labels to each of them
    n = 0
    new_node_labels = []

    def _add_node(
        graph: nx.Graph,
        node_attr: dict,
        global_id: int,
        node_id: int,
        node_nation: str,
    ):
        graph.add_node(global_id)
        for attr in ["type", "color", "intermediary", "weight", "showLabel"]:
            if attr in node_attr:
                graph.nodes[global_id][attr] = node_attr[attr]
        graph.nodes[global_id]["country"] = node_nation
        # labels are generated here but attached later (to have the generator work on a simple flat numeric namespace)
        new_node_labels.append(
            node_attr["label"].format(nation=node_nation, id=node_id + 1),
        )

    for node_attributes in subnetwork["network_nodes"]:
        node_type = NodeType(node_attributes["type"])
        if node_type == NodeType.CENTRAL_BANK and unique_cb:
            # add only one central bank for all nations
            _add_node(g, node_attributes, n, 0, EU_COUNTRY_CODE)
            n += 1
        else:
            for nation in nations:
                for i in range(node_attributes["count"][nation]):
                    _add_node(g, node_attributes, n, i, nation)
                    n += 1

    # We add the proper source->target arcs using the corrisponding random model
    (arc_generator, arc_generator_params) = subnetwork["network_model"]
    arc_generator_args = []
    for node_set_feature in subnetwork["network_nodes"]:
        if node_set_feature["type"] == NodeType.CENTRAL_BANK.value and unique_cb:
            arc_generator_args.append(1)
        else:
            if len(nations) > 1:
                arc_generator_args.append(sum(node_set_feature["count"].values()))
            else:
                nation = nations[0]
                arc_generator_args.append(node_set_feature["count"][nation])
    arc_generator_params["rnd_seed"] = rnd_seed
    arc_generator(
        g,
        (
            subnetwork["network_ekey"]
            if len(nations) > 1
            else subnetwork["network_ekey"].format(nation=nations[0])
        ),
        arc_generator_params,
        *arc_generator_args,
    )

    # Generating attributed (capacitiy, fees, ...) and their values for (direct) channels
    for attribute_label, (
        attribute_value_generator,
        attribute_value_generator_params,
    ) in subnetwork["[edge]"].items():
        attribute_value_generator(
            g,
            label=attribute_label,
            params=attribute_value_generator_params,
        )

    # Generating attributed (capacitiy, fees, ...) and their values for (inverse) channels (if they exist)
    # The subnetwork model may specify that all channels must have a matching channel in the opposite target->source direction
    # (with the same random model for the capacity of such inverse channels)
    g_incoming = g.reverse(copy=True)
    for attribute_label, (
        attribute_value_generator,
        attribute_value_generator_params,
    ) in subnetwork["[edge]"].items():
        if attribute_label == "capacity":
            # for the reverse edge, we use the same value sampled for the forward edge
            continue
        attribute_value_generator(
            g_incoming,
            label=attribute_label,
            params=attribute_value_generator_params,
        )

    # set balances according to the network_bidir flag
    _set_balances(g, g_incoming, subnetwork)
    g = nx.compose(g, g_incoming)

    # Numeric node labels are replaced with symbolic names at this stage
    label_mapping = dict(zip(g.nodes(), new_node_labels, strict=False))
    return nx.relabel_nodes(g, label_mapping)


def postprocess_plasma_network(network, cmdline_flags):
    # Computing the gas balance each plasma node needs to open all its channels
    fee_to_open_one_channel = eu(
        "3",
    )  # It is 2.23eu "usually"; should not be hard coded but computed somehow.
    balance = defaultdict(lambda: 0)
    for u, _v, wt in network.edges.data("balance"):
        if wt is not None:
            balance[u] += wt + fee_to_open_one_channel
    balances = {
        idx: {"pre_channel_balance": float_round(balance[idx], direction="up")}
        for idx in balance
    }
    nx.set_node_attributes(network, balances)

    # Distributing plasma nodes across machines in a multi-machine deploy in such a way as to maximize the cost of the onion routing hops
    """
    # Commenting this out because it takes too long and it's currently not used
    kcut = approx_max_cut(network, k=cmdline_flags["deploy_node_count"])
    node_to_machine = {n:{"deploy_to":idx_to_alphabetical(bucket_idx)} for bucket_idx in range(len(kcut)) for n in kcut[bucket_idx]}
    nx.set_node_attributes(network, node_to_machine)
    """
