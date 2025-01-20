########################################################################################################################
#                                      Model parameters and their default values                                       #
########################################################################################################################

default_rnd_model_params = {
    # "number_of_nodes_in_simulation"     : 330031, # Number of nodes in default simulation; actual Eurosystem value: approx 360M
    "number_of_CBs_in_simulation": 1,  # We default 4 CBs; actual Eurosystem value: approx 500
    "intermediary_to_CB_ratio": 10,  # We default 3 citizens per intermediary; actual Eurosystem value: approx 500
    "fraction_of_unbanked_retail_users": 0,
    "number_of_retail_users_in_simulation": 100000,
    "number_of_merchants_in_simulation": 10000,
    "p_small_merchants": 0.4,
    "p_medium_merchants": 0.3,
    "p_large_merchants": 0.3,
}


# The following function extends the parameters given as input or present in the defaults to other (dependent) parameters
def infer_missing_rnd_model_params(rnd_model_params):
    functional_dependencies = {
        0: ("number_of_nodes_in_simulation", [lambda v: v(1) + v(2) + v(3) + v(4)]),
        1: (
            "number_of_CBs_in_simulation",
            [
                lambda v: v(0) - v(2) - v(3) - v(4),
                lambda v: int(v(2) / v(6)),
                lambda v: int(v(3) / v(7)),
            ],
        ),
        2: (
            "number_of_intermediaries_in_simulation",
            [
                lambda v: v(0) - v(1) - v(3) - v(4),
                lambda v: int(v(3) / v(5)),
                lambda v: int(v(1) * v(6)),
            ],
        ),
        3: (
            "number_of_retail_users_in_simulation",
            [
                lambda v: v(0) - v(1) - v(2) - v(4),
                lambda v: int(v(0) - v(1) - v(2) - int((v(0) - v(1) - v(2)) * v(8))),
                lambda v: int(v(2) * v(5)),
                lambda v: int(v(1) * v(7)),
                lambda v: int(v(9) + v(10)),
            ],
        ),
        4: (
            "number_of_merchants_in_simulation",
            [lambda v: v(0) - v(1) - v(2) - v(3), lambda v: int(v(3) * v(8))],
        ),
        5: ("citizens_to_intermediary_ratio", [lambda v: v(3) / v(2)]),
        6: ("intermediary_to_CB_ratio", [lambda v: v(2) / v(1)]),
        7: ("citizens_to_CB_ratio", [lambda v: v(3) / v(1)]),
        8: ("merchants_to_retail_users_ratio", [lambda v: v(4) / v(3)]),
        9: ("number_of_banked_retail_users_in_simulation", [lambda v: v(3) - v(10)]),
        10: (
            "number_of_unbanked_retail_users_in_simulation",
            [lambda v: v(3) - v(9), lambda v: round(v(3) * v(11))],
        ),
        11: ("fraction_of_unbanked_retail_users", [lambda v: round(v(10) / v(3))]),
        12: ("p_small_merchants", [lambda v: v(12)]),
        13: ("p_medium_merchants", [lambda v: v(13)]),
        14: ("p_large_merchants", [lambda v: v(14)]),
    }

    # List of names of all params we have to know the value of, whether inferred or given as input
    set_of_required_params = {fd[0] for fd in functional_dependencies.values()}

    fixpoint = False
    while not set_of_required_params.issubset(set(rnd_model_params)):
        n_params_already_assigned = len(rnd_model_params)
        for output_p_idx in functional_dependencies:
            (output_p, list_of_computations) = functional_dependencies[output_p_idx]

            def value_of_param_at_idx(idx):
                (name, _) = functional_dependencies[idx]
                return rnd_model_params[name]

            if output_p not in rnd_model_params:
                if list_of_computations is not None:
                    for computation in list_of_computations:
                        try:
                            rnd_model_params[output_p] = computation(
                                value_of_param_at_idx,
                            )
                        except KeyError:
                            continue
                if fixpoint and output_p not in rnd_model_params:
                    try:
                        rnd_model_params[output_p] = default_rnd_model_params[output_p]
                    except KeyError:
                        continue
        if n_params_already_assigned == len(rnd_model_params):
            if fixpoint and len(rnd_model_params) < len(functional_dependencies):
                print("Some functional dependency missing; could only compute:")
                print(rnd_model_params)
                exit(-1)
            fixpoint = True
    return rnd_model_params
