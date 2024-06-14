import networkx as nx
import numpy as np
import scipy.stats

import plasma_network_generator.utils as utils
from plasma_network_generator.core import ChannelType

########################################################################################################################
#                              Random graph models used to generate individual subnetworks                             #
########################################################################################################################


# A clique, where channels exist between each node and each other node
def clique(g, edge_key_template, rnd_model_params, *_number_of_nodes):
    number_of_nodes = sum(_number_of_nodes)
    c = nx.complete_graph(number_of_nodes)
    _update_rekeying_edges(g, c, edge_key_template)


# A typical small-world subnetwork model
def watts_strogatz(g, edge_key_template, rnd_model_params, *_number_of_nodes):
    number_of_nodes = sum(_number_of_nodes)
    k = (
        rnd_model_params["k"]
        if rnd_model_params["k"] < number_of_nodes
        else number_of_nodes
    )  # For very small graphs
    ws = nx.watts_strogatz_graph(
        n=number_of_nodes,
        k=k,
        p=rnd_model_params["p"],
        seed=rnd_model_params["rnd_seed"],
    )
    _update_rekeying_edges(g, ws, edge_key_template)


# A random subnetwork model
def erdos_renyi(g, edge_key_template, rnd_model_params, *_number_of_nodes):
    number_of_nodes = sum(_number_of_nodes)
    er = nx.erdos_renyi_graph(
        n=number_of_nodes,
        p=rnd_model_params["p"],
        directed=False,
        seed=rnd_model_params["rnd_seed"],
    )
    _update_rekeying_edges(g, er, edge_key_template)


# A bipartite graph where each node in the "up_nodes" is associated to one element of a partition of the "down_nodes"
# and the partition is such that its subset have a size with a lognormal distribution
def bipartite_lognormal_partition(
    g,
    edge_key_template,
    rnd_model_params,
    number_of_up_nodes,
    number_of_down_nodes,
):
    idx_range_of_down_nodes = list(
        range(number_of_up_nodes, number_of_up_nodes + number_of_down_nodes),
    )
    intermediary_partition = zip(
        list(range(number_of_up_nodes)),
        lognormal_set_partition(
            idx_range_of_down_nodes,
            number_of_up_nodes,
            mean=rnd_model_params["mean"],
            sigma=rnd_model_params["sigma"],
        ),
        strict=False,
    )
    edges = [
        (cb, intermediary)
        for (cb, intermediary_list) in intermediary_partition
        for intermediary in intermediary_list
    ]
    _add_rekeyed_edges(g, edges, edge_key_template)


def bipartite_erdos_renyi(
    g,
    edge_key_template,
    rnd_model_params,
    number_of_up_nodes,
    number_of_down_nodes,
):
    idx_range_of_up_nodes = list(range(number_of_up_nodes))
    idx_range_of_down_nodes = list(
        range(number_of_up_nodes, number_of_up_nodes + number_of_down_nodes),
    )
    all_edges = [(a, b) for a in idx_range_of_up_nodes for b in idx_range_of_down_nodes]
    edge_selection = np.random.choice(
        a=[True, False],
        size=len(all_edges),
        p=[rnd_model_params["p"], 1 - rnd_model_params["p"]],
    )
    selected_edges = [
        edge
        for (edge, selected) in zip(all_edges, edge_selection, strict=False)
        if selected
    ]
    _add_rekeyed_edges(g, selected_edges, edge_key_template)


########################################################################################################################
#                                                  NetworkX utils                                                      #
########################################################################################################################


def _update_rekeying_edges(g_target, g_source, key_template):
    g_target.add_edges_from(
        [
            (a, b, key_template.format(id=key))
            for ((a, b), key) in zip(
                g_source.edges(),
                list(range(g_source.number_of_edges())),
                strict=False,
            )
        ],
    )


def _add_rekeyed_edges(g, edges, key_template):
    g.add_edges_from(
        [
            (a, b, key_template.format(id=key))
            for ((a, b), key) in zip(edges, list(range(len(edges))), strict=False)
        ],
    )


########################################################################################################################
#                         Random capacity models for channels in a given subnetwork                                    #
########################################################################################################################


def _box(x):
    return list(x) if type(x) is tuple else x if isinstance(x, list) else [x]


# Supports multi-labels associated to multiple-params, all of which have a fixed values for all edges
def fixed(g, label, params):
    attribute_label_to_attribute_value = dict(
        zip(_box(label), _box(params), strict=False)
    )
    edge_to_attribute_label_to_attribute_value = dict(
        zip(
            g.edges,
            [attribute_label_to_attribute_value] * g.number_of_edges(),
            strict=False,
        ),
    )
    nx.set_edge_attributes(g, edge_to_attribute_label_to_attribute_value)


def varying(g, label, params):
    national_attr = {label: params[ChannelType.NATIONAL.value]}
    international_attr = {label: params[ChannelType.INTERNATIONAL.value]}
    edge_to_attribute_label_to_attribute_value = dict(
        zip(
            g.edges,
            [
                (
                    national_attr
                    if g.nodes[u]["country"] == g.nodes[v]["country"]
                    else international_attr
                )
                for u, v, key in g.edges
            ],
            strict=False,
        ),
    )
    nx.set_edge_attributes(g, edge_to_attribute_label_to_attribute_value)


def enumeration(g, label, params):
    n = g.number_of_edges()
    attribute_label_to_attribute_value = dict(
        zip(g.edges, [{label: params.format(id=i)} for i in range(n)], strict=False),
    )
    nx.set_edge_attributes(g, attribute_label_to_attribute_value)


# Assumes one label for one param to generate at random, uniformly within "min" and "max"
def uniform(g, label, params):
    capacities = np.random.uniform(
        low=100 * params["min"],
        high=100 * params["max"],
        size=g.number_of_edges(),
    )
    centrounded_capacities = [int(c) / 100.0 for c in capacities]
    edge_to_capacity = dict(zip(g.edges, centrounded_capacities, strict=False))
    nx.set_edge_attributes(g, edge_to_capacity, name=label)


def exponential(g, label, params):
    list_of_attribute_labels = _box(label)
    list_of_attribute_means = _box(params["mean"])
    list_of_attribute_value_significant_digits = (
        params["digits"] if "digits" in params else [2] * len(list_of_attribute_means)
    )

    low_cap = params.get("low_cap", 0.0)
    lists_of_random_values = [
        capped_and_rounded_exponential(
            scale=mean,
            size=g.number_of_edges(),
            n_digits=n_digits,
            low_cap=low_cap,
        )
        for (mean, n_digits) in zip(
            list_of_attribute_means,
            list_of_attribute_value_significant_digits,
            strict=False,
        )
    ]
    list_of_random_value_tuples = [
        [list_of_randomValues[i] for list_of_randomValues in lists_of_random_values]
        for i in range(g.number_of_edges())
    ]

    list_of_attribute_label_to_random_value = [
        dict(zip(list_of_attribute_labels, randomValueTuples, strict=False))
        for randomValueTuples in list_of_random_value_tuples
    ]
    edge_to_attribute_label_to_attribute_value = dict(
        zip(g.edges, list_of_attribute_label_to_random_value, strict=False),
    )
    nx.set_edge_attributes(g, edge_to_attribute_label_to_attribute_value)


def beta(g, label, params):
    beta = custom_beta_distribution(
        min_val=params["min"],
        max_val=params["max"],
        mean=params["mean"],
        std=params["dev"],
    )
    capacities = beta.rvs(size=g.number_of_edges())
    centrounded_capacities = [utils.float_round(c) for c in capacities]
    edge_to_capacity = dict(zip(g.edges, centrounded_capacities, strict=False))
    nx.set_edge_attributes(g, edge_to_capacity, name=label)


# Supports multi-labels associated to multiple-params, for which a tuple of random variables are generated
# compliant with the custom, discrete, joint probability distribution provided
def custom_discrete(g, label, params):
    attribute_labels = _box(label)
    probabilities, tuples_of_values = zip(*params, strict=False)
    indexes_of_tuples_of_values = list(range(len(tuples_of_values)))
    list_of_random_indexes_of_tuples_of_values = np.random.choice(
        indexes_of_tuples_of_values,
        g.number_of_edges(),
        p=probabilities,
    )
    list_of_random_tuples_of_values = [
        list(tuples_of_values[i]) for i in list_of_random_indexes_of_tuples_of_values
    ]
    list_of_attribute_label_and_random_attribute_value = list(
        zip(
            [attribute_labels] * g.number_of_edges(),
            list_of_random_tuples_of_values,
            strict=False,
        ),
    )
    list_of_attribute_label_to_random_attribute_value_dict = [
        dict(zip(labels, values, strict=False))
        for (labels, values) in list_of_attribute_label_and_random_attribute_value
    ]
    edge_to_attribute_label_to_attribute_value = dict(
        zip(
            g.edges,
            list_of_attribute_label_to_random_attribute_value_dict,
            strict=False,
        ),
    )
    nx.set_edge_attributes(g, edge_to_attribute_label_to_attribute_value)


########################################################################################################################
#                                            Custom distributions                                                      #
########################################################################################################################


def capped_and_rounded_exponential(scale, size, n_digits, low_cap=0):
    realization = np.random.exponential(scale, size)
    realization = (max(float(low_cap), value) for value in realization)
    return [utils.float_round(v, n_digits) for v in realization]


# See https://stackoverflow.com/questions/50626710/generating-random-numbers-with-predefined-mean-std-min-and-max
def custom_beta_distribution(min_val, max_val, mean, std):
    scale = max_val - min_val
    location = min_val
    # Mean and standard deviation of the unscaled beta distribution
    unscaled_mean = (mean - min_val) / scale
    unscaled_var = (std / scale) ** 2
    # Computation of alpha and beta can be derived from mean and variance formulas
    t = unscaled_mean / (1 - unscaled_mean)
    beta = ((t / unscaled_var) - (t * t) - (2 * t) - 1) / (
        (t * t * t) + (3 * t * t) + (3 * t) + 1
    )
    alpha = beta * t
    # Not all parameters may produce a valid distribution
    if alpha <= 0 or beta <= 0:
        msg = "Cannot create distribution for the given parameters."
        raise ValueError(msg)
    # Make scaled beta distribution with computed parameters
    return scipy.stats.beta(alpha, beta, scale=scale, loc=location)


########################################################################################################################
#                                       Non-uniform set partitioning                                                   #
########################################################################################################################


def lognormal_set_partition(
    set_to_partition,
    number_of_partitions,
    mean=0.0,
    sigma=1.0,
):
    # We sample a lognormal distribution
    intermediaries_per_cb_distribution = sorted(
        np.random.lognormal(mean, sigma, size=number_of_partitions),
        reverse=True,
    )

    # Build an approximate size for each component of the partition	based on the samples of a lognormal rnd variable
    partition_size = [
        max(
            1,
            round(x * len(set_to_partition) / sum(intermediaries_per_cb_distribution)),
        )
        for x in intermediaries_per_cb_distribution
    ]

    # We make the partition exact wrt the size of the input set to partition
    for i in range(len(partition_size)):
        partition_size[i] += (
            (-1)
            if sum(partition_size) > len(set_to_partition)
            else (+1) if sum(partition_size) < len(set_to_partition) else 0
        )

    # We partition the input set according the previously computed size for its components
    result = []
    for n in partition_size:
        result.append(set_to_partition[:n])
        set_to_partition = set_to_partition[n:]

    return result
