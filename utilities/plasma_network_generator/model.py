import plasma_network_generator.rnd as rnd
import plasma_network_generator.utils as utils
from plasma_network_generator.core import ChannelType, NodeType

########################################################################################################################
#                     There are 5 different random (sub)networks within and among 3 layers of nodes                    #
########################################################################################################################


def payment_subnetworks_random_models(rnd_model_params):
    layer_nodes = {
        # Nodes in Layer 1: Central Banks
        "layer1": {
            "count": rnd_model_params["number_of_CBs_in_simulation"],
            "type": NodeType.CENTRAL_BANK.value,
            "label": "CB{id}" if rnd_model_params["unique_cb"] else "CB{nation}{id}",
            "color": "blue",
            "country": "",
            "weight": rnd_model_params['layer_nodes']['layer1']['weight'],
            "showLabel": True,
        },
        # Nodes in Layer 2: Intermediaries
        "layer2": {
            "count": rnd_model_params["number_of_intermediaries_in_simulation"],
            "type": NodeType.INTERMEDIARY.value,
            "label": "Intermediary{nation}{id}",
            "color": "red",
            "country": "",
            "weight": rnd_model_params['layer_nodes']['layer2']['weight'],
            "showLabel": True,
        },
        # Nodes in Layer 3: Retail users
        # Sub-layer 3B: Banked users
        "layer3B": {
            "count": rnd_model_params["number_of_banked_retail_users_in_simulation"],
            "type": NodeType.RETAIL_BANKED.value,
            "label": "Retail{nation}{id}",
            "color": "dark green",
            "country": "",
            "intermediary": "",
            "weight": rnd_model_params['layer_nodes']['layer3B']['weight'],
            "showLabel": False,
        },
        # Sub-layer 3U: Unbanked users
        "layer3U": {
            "count": rnd_model_params["number_of_unbanked_retail_users_in_simulation"],
            "type": NodeType.RETAIL_UNBANKED.value,
            "label": "Unbanked{nation}{id}",
            "color": "light green",
            "country": "",
            "showLabel": False,
        },
        # Sub-layer 3Msmall: SMALL Merchant users
        "layer3Msmall": {
            "count": rnd_model_params["number_of_small_merchants_in_simulation"],
            "type": NodeType.MERCHANT_SMALL.value,
            "label": "Merchant-small-{nation}{id}",
            "color": "yellow",
            "country": "",
            "intermediary": "",
            "weight": rnd_model_params['layer_nodes']['layer3Msmall']['weight'],
            "showLabel": False,
        },
        # Sub-layer 3Mmedium: MEDIUM Merchant users
        "layer3Mmedium": {
            "count": rnd_model_params["number_of_medium_merchants_in_simulation"],
            "type": NodeType.MERCHANT_MEDIUM.value,
            "label": "Merchant-medium-{nation}{id}",
            "color": "yellow",
            "country": "",
            "intermediary": "",
            "weight": rnd_model_params['layer_nodes']['layer3Mmedium']['weight'],
            "showLabel": False,
        },
        # Sub-layer 3Mlarge: LARGE Merchant users
        "layer3Mlarge": {
            "count": rnd_model_params["number_of_large_merchants_in_simulation"],
            "type": NodeType.MERCHANT_LARGE.value,
            "label": "Merchant-large-{nation}{id}",
            "color": "yellow",
            "country": "",
            "intermediary": "",
            "weight": rnd_model_params['layer_nodes']['layer3Mlarge']['weight'],
            "showLabel": False,
        },
    }

    subnetworks_models = {
        # Layer 1: Central Banks and the clique of channels among them
        "[1<channel>1]": {
            "ID": "channels_among_CBs",
            "description": "Network of channels among nodes managed by CBs",
            "type": ChannelType.INTERNATIONAL.value,
            "network": {
                "type": "MultiDiGraph",
                "ekey": "l1.l1.{id}",
                "model": (
                    (lambda *a, **k: None, {})  # noqa: ARG005
                    if rnd_model_params["unique_cb"]
                    else (rnd.clique, {})
                ),
                "nodes": [layer_nodes["layer1"]],
                "bidir": True,  # For each channel opened in one direction, a symmetric channel in the opposite direction is also opened
            },
            "[edge]": {
                "type": (rnd.fixed, "1<>1"),
                "capacity": (
                    rnd.fixed,
                    utils.eu(
                        rnd_model_params["subnetworks"]["[1<channel>1]"]["capacity"]
                    ),
                ),  # Channels between CBs all have this large, fixed capacity
                "routing_fee": {  # There are no fees on channels among CBs
                    "source": {("base", "rate"): (rnd.fixed, [0.0, 0.0])},
                    "target": {("base", "rate"): (rnd.fixed, [0.0, 0.0])},
                },
                "is_private": (
                    rnd.fixed,
                    False,
                ),  # layer1 channels are public by default
                "weight": (rnd.fixed, rnd_model_params["subnetworks"]["[1<channel>1]"]["weight"]),
            },
        },
        # Layer 2: intermediaries and their intra-layer payment channel connections
        "[2<channel>2]": {
            "ID": "channels_among_intermediaries",
            "description": "Network of channels among nodes managed by intermediaries",
            "type": ChannelType.INTERNATIONAL.value,
            "network": {
                "type": "MultiDiGraph",
                "ekey": "l2.l2.{id}",
                "model": (
                    rnd.watts_strogatz,
                    {"k": utils.Δ("i2i_k") > 4, "p": utils.Δ("i2i_p") > 0.1},
                ),
                "nodes": [layer_nodes["layer2"]],
                "bidir": True,  # For each channel opened in one direction, a symmetric channel in the opposite direction is also opened
            },
            "[edge]": {
                "type": (rnd.fixed, "2<>2"),
                "capacity": (
                    rnd.fixed,
                    utils.eu(
                        rnd_model_params["subnetworks"]["[2<channel>2]"]["capacity"]
                    ),
                ),  # Channels between two intermediaries all have this capacity
                "routing_fee": {
                    "source": {
                        ("base", "rate"): (
                            rnd.custom_discrete,
                            [
                                (0.5, (utils.eu("0.2cent"), utils.eu("0.015%"))),
                                (0.5, (utils.eu("0.25cent"), utils.eu("0.01%"))),
                            ],
                        ),
                    },
                    "target": {
                        ("base", "rate"): (
                            rnd.custom_discrete,
                            [
                                (0.5, (utils.eu("0.2cent"), utils.eu("0.015%"))),
                                (0.5, (utils.eu("0.25cent"), utils.eu("0.01%"))),
                            ],
                        ),
                    },
                },
                "is_private": (
                    rnd.fixed,
                    False,
                ),  # layer2 channels are public by default
                "weight": (
                    rnd.varying,
                    {
                        ChannelType.NATIONAL.value: rnd_model_params["subnetworks"]["[2<channel>2]"]["weight"]["national"],
                        ChannelType.INTERNATIONAL.value: rnd_model_params["subnetworks"]["[2<channel>2]"]["weight"]["international"],
                    },
                ),
            },
        },
        # Layer 1<->2: payment channels among CBs and intermediaries
        "[1<channel>2]": {
            "ID": "channels_between_CBS_and_intemediaries",
            "description": "Network of channels linking CB nodes with intermediary nodes",
            "type": (
                ChannelType.INTERNATIONAL.value
                if rnd_model_params["unique_cb"]
                else ChannelType.NATIONAL.value
            ),
            "network": {
                "type": "MultiDiGraph",
                "ekey": (
                    "l1.l2.{id}"
                    if rnd_model_params["unique_cb"]
                    else "l1.l2.{nation}.{{id}}"
                ),
                "model": (
                    rnd.bipartite_lognormal_partition,
                    {"mean": 0.0, "sigma": 1.0},
                ),
                "nodes": [layer_nodes["layer1"], layer_nodes["layer2"]],
                "bidir": True,  # For each channel opened in one direction, a symmetric channel in the opposite direction is also opened
            },
            "[edge]": {
                "type": (rnd.fixed, "1<>2"),
                # Channels between a CB and an intermediary all have this large, fixed capacity
                "capacity": (
                    rnd.fixed,
                    utils.eu(
                        rnd_model_params["subnetworks"]["[1<channel>2]"]["capacity"]
                    ),
                ),
                "routing_fee": {  # There are no fees on channels among CBs and intermediaries
                    "source": {("base", "rate"): (rnd.fixed, [0.0, 0.0])},
                    "target": {("base", "rate"): (rnd.fixed, [0.0, 0.0])},
                },
                "is_private": (
                    rnd.fixed,
                    False,
                ),  # layer1-to-layer2 channels are public by default
                "weight": (rnd.fixed, rnd_model_params["subnetworks"]["[1<channel>2]"]["weight"]),
            },
        },
        # Layer 2->3: payment channels from intermediaries to retail end users
        "[2<channel>3B]": {
            "ID": "channels_among_intermediaries_and_retail_users_banked",
            "description": "Network of channels linking intermediaries and banked citizens",
            "type": ChannelType.NATIONAL.value,
            "network": {
                "type": "MultiDiGraph",
                "ekey": "l2.l3B.{nation}.{{id}}",
                "nodes": [layer_nodes["layer2"], layer_nodes["layer3B"]],
                "model": (
                    rnd.bipartite_lognormal_partition,
                    {"mean": 0.0, "sigma": 1.0},
                ),
                # A channel from a retail user to an intermediaary is also put in place
                # to simulate a non-zero initial balance "at intermediaries accounts" for retail nodes:
                "bidir": True,
            },
            "[edge]": {
                "type": (rnd.fixed, "2<>3B"),
                # The capacity of unidirectional channels from an intermediary to a retail user is generated according to
                # a uniform flat distribution between this min and max values (think "min/max withdrawal plafond")
                "capacity": (
                    rnd.fixed,
                    utils.eu(
                        rnd_model_params["subnetworks"]["[2<channel>3B]"]["capacity"]
                    ),
                ),
                "routing_fee": {
                    "source": {
                        ("base", "rate"): (
                            rnd.custom_discrete,
                            [
                                (0.5, (utils.eu("0.2cent"), utils.eu("0.5%"))),
                                (0.5, (utils.eu("0.15cent"), utils.eu("0.6%"))),
                            ],
                        ),
                    },
                    "target": {
                        ("base", "rate"): (
                            rnd.exponential,
                            {
                                "mean": [utils.eu("0.2cent"), utils.eu("0.5%")],
                                "digits": [4, 8],
                            },
                        ),
                    },
                },
                "is_private": (
                    rnd.fixed,
                    True,
                ),  # layer2-to-layer3B channels are private by default
                "weight": (rnd.fixed, rnd_model_params["subnetworks"]["[2<channel>3B]"]["weight"]),
            },
        },
        # Layer 2->3: payment channels from intermediaries to retail end users (merchants small)
        "[2<channel>3Msmall]": {
            "ID": "channels_among_intermediaries_and_retail_users_merchant_small",
            "description": "Network of channels linking intermediaries and small merchants",
            "type": ChannelType.NATIONAL.value,
            "network": {
                "type": "MultiDiGraph",
                "ekey": "l2.l3Msmall.{nation}.{{id}}",
                "nodes": [layer_nodes["layer2"], layer_nodes["layer3Msmall"]],
                "model": (
                    rnd.bipartite_lognormal_partition,
                    {"mean": 0.0, "sigma": 1.0},
                ),
                # A channel from a retail user to an intermediaary is also put in place
                # to simulate a non-zero initial balance "at intermediaries accounts" for retail nodes:
                "bidir": True,
            },
            "[edge]": {
                "type": (rnd.fixed, "2<>3Msmall"),
                # The capacity of unidirectional channels from an intermediary to a retail user is generated according to
                # a uniform flat distribution between this min and max values (think "min/max withdrawal plafond")
                "capacity": (
                    rnd.fixed,
                    utils.eu(
                        rnd_model_params["subnetworks"]["[2<channel>3Msmall]"][
                            "capacity"
                        ],
                    ),
                ),
                "routing_fee": {
                    "source": {
                        ("base", "rate"): (
                            rnd.custom_discrete,
                            [
                                (0.5, (utils.eu("0.2cent"), utils.eu("0.5%"))),
                                (0.5, (utils.eu("0.15cent"), utils.eu("0.6%"))),
                            ],
                        ),
                    },
                    "target": {
                        ("base", "rate"): (
                            rnd.exponential,
                            {
                                "mean": [utils.eu("0.2cent"), utils.eu("0.5%")],
                                "digits": [4, 8],
                            },
                        ),
                    },
                },
                "is_private": (
                    rnd.fixed,
                    True,
                ),  # layer2-to-layer3Ms channels are private by default
                "weight": (rnd.fixed, rnd_model_params["subnetworks"]["[2<channel>3Msmall]"]["weight"]),
            },
        },
        # Layer 2->3: payment channels from intermediaries to retail end users (merchants medium)
        "[2<channel>3Mmedium]": {
            "ID": "channels_among_intermediaries_and_retail_users_merchant_medium",
            "description": "Network of channels linking intermediaries and medium merchants",
            "type": ChannelType.NATIONAL.value,
            "network": {
                "type": "MultiDiGraph",
                "ekey": "l2.l3Mmedium.{nation}.{{id}}",
                "nodes": [layer_nodes["layer2"], layer_nodes["layer3Mmedium"]],
                "model": (
                    rnd.bipartite_lognormal_partition,
                    {"mean": 0.0, "sigma": 1.0},
                ),
                # A channel from a retail user to an intermediaary is also put in place
                # to simulate a non-zero initial balance "at intermediaries accounts" for retail nodes:
                "bidir": True,
            },
            "[edge]": {
                "type": (rnd.fixed, "2<>3Mmedium"),
                # The capacity of unidirectional channels from an intermediary to a retail user is generated according to
                # a uniform flat distribution between this min and max values (think "min/max withdrawal plafond")
                "capacity": (
                    rnd.fixed,
                    utils.eu(
                        rnd_model_params["subnetworks"]["[2<channel>3Mmedium]"][
                            "capacity"
                        ],
                    ),
                ),
                "routing_fee": {
                    "source": {
                        ("base", "rate"): (
                            rnd.custom_discrete,
                            [
                                (0.5, (utils.eu("0.2cent"), utils.eu("0.5%"))),
                                (0.5, (utils.eu("0.15cent"), utils.eu("0.6%"))),
                            ],
                        ),
                    },
                    "target": {
                        ("base", "rate"): (
                            rnd.exponential,
                            {
                                "mean": [utils.eu("0.2cent"), utils.eu("0.5%")],
                                "digits": [4, 8],
                            },
                        ),
                    },
                },
                "is_private": (
                    rnd.fixed,
                    True,
                ),  # layer2-to-layer3Mm channels are private by default
                "weight": (rnd.fixed, rnd_model_params["subnetworks"]["[2<channel>3Mmedium]"]["weight"]),
            },
        },
        # Layer 2->3: payment channels from intermediaries to retail end users (merchants large)
        "[2<channel>3Mlarge]": {
            "ID": "channels_among_intermediaries_and_retail_users_merchant_large",
            "description": "Network of channels linking intermediaries and large merchants",
            "type": ChannelType.NATIONAL.value,
            "network": {
                "type": "MultiDiGraph",
                "ekey": "l2.l3Mlarge.{nation}.{{id}}",
                "nodes": [layer_nodes["layer2"], layer_nodes["layer3Mlarge"]],
                "model": (
                    rnd.bipartite_lognormal_partition,
                    {"mean": 0.0, "sigma": 1.0},
                ),
                # A channel from a retail user to an intermediaary is also put in place
                # to simulate a non-zero initial balance "at intermediaries accounts" for retail nodes:
                "bidir": True,
            },
            "[edge]": {
                "type": (rnd.fixed, "2<>3Mlarge"),
                # The capacity of unidirectional channels from an intermediary to a retail user is generated according to
                # a uniform flat distribution between this min and max values (think "min/max withdrawal plafond")
                "capacity": (
                    rnd.fixed,
                    utils.eu(
                        rnd_model_params["subnetworks"]["[2<channel>3Mlarge]"][
                            "capacity"
                        ],
                    ),
                ),
                "routing_fee": {
                    "source": {
                        ("base", "rate"): (
                            rnd.custom_discrete,
                            [
                                (0.5, (utils.eu("0.2cent"), utils.eu("0.5%"))),
                                (0.5, (utils.eu("0.15cent"), utils.eu("0.6%"))),
                            ],
                        ),
                    },
                    "target": {
                        ("base", "rate"): (
                            rnd.exponential,
                            {
                                "mean": [utils.eu("0.2cent"), utils.eu("0.5%")],
                                "digits": [4, 8],
                            },
                        ),
                    },
                },
                "is_private": (
                    rnd.fixed,
                    True,
                ),  # layer2-to-layer3Ml channels are private by default
                "weight": (rnd.fixed, rnd_model_params["subnetworks"]["[2<channel>3Mlarge]"]["weight"]),
            },
        },
    }

    # Layer 3: retail end users (citizens, including banked and unbanked) and their intra-layer payment channel connections
    if rnd_model_params["subnetworks"]["[3<channel>3]"]["enabled"]:
        subnetworks_models |= {
            "[3<channel>3]" : {
                "ID" : "channels_among_citizens",
                "description"  : "Network of P2P channels among citizens",
                "network" : {
                    "type"  : "MultiDiGraph",
                    "ekey"  : "l3.l3.{}",
                    "nodes" : [layer_nodes["layer3B"],layer_nodes["layer3U"]],
                    "model" : (rnd.watts_strogatz, {
                        "k" : utils.Δ("p2p_k") > 4,
                        "p" : utils.Δ("p2p_p") > 0.10
                    }),
                    "bidir" : False # P2P network where users do not necessarily reciprocate the opening of a channel
                },
                "[edge]" : {
                    "type" : (rnd.fixed, "3<>3"),
                    # The capacity of unidirectional P2P channels retail users establish among themselves
                    # is generated according to an exponential distribution with the given average value
                    "capacity" : (rnd.beta, {
                        "min"  : utils.Δ("minP2Pcapacity")  > utils.eu(rnd_model_params["subnetworks"]["[3<channel>3]"]["capacity"]["min"]),
                        "mean" : utils.Δ("meanP2Pcapacity") > utils.eu(rnd_model_params["subnetworks"]["[3<channel>3]"]["capacity"]["mean"]),
                        "max"  : utils.Δ("maxP2Pcapacity")  > utils.eu(rnd_model_params["subnetworks"]["[3<channel>3]"]["capacity"]["max"]),
                        "dev"  : utils.Δ("devP2Pcapacity")  > utils.eu(rnd_model_params["subnetworks"]["[3<channel>3]"]["capacity"]["dev"])}),
                    "routing_fee" : {
                        "source" : { ("base","rate") : (rnd.exponential, {"mean" : [utils.eu("0.2cent"), utils.eu("0.02%")], "digits":[4,8]}) },
                        "target" : { ("base","rate") : (rnd.exponential, {"mean" : [utils.eu("0.2cent"), utils.eu("0.02%")], "digits":[4,8]}) }
                    },
                    "is_private": (
                        rnd.fixed,
                        True,
                    ),  # layer1-to-layer2 channels are private by default
                    "weight": (rnd.fixed, rnd_model_params["subnetworks"]["[3<channel>3]"]["weight"]),
                }
            },
        }

    return (layer_nodes, subnetworks_models)
