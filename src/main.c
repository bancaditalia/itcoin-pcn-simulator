//The C main file for a ROSS model
//This file includes:
// - definition of the LP types
// - command line argument setup
// - a main function

//includes
#include "features/routing.h"

#include "model/blockchain.h"
#include "model/global.h"
#include "model/pcn_node.h"
#include "model/load.h"
#include "model/event_trace.h"
#include "model/message.h"

#include "utils/array.h"
#include "utils/heap.h"
#include "utils/list.h"
#include "utils/utils.h"

// Define LP types
//   these are the functions called by ROSS for each LP
//   multiple sets can be defined (for multiple LP types)
tw_lptype model_lps[] = {
  {
    (init_f) model_init,
    (pre_run_f) NULL,
    (event_f) model_event,
    (revent_f) model_event_reverse,
    (commit_f) model_commit,
    (final_f) model_final,
    (map_f) metis_map,
    sizeof(node*)
  },
  {
    (init_f) blockchain_init,
    (pre_run_f) NULL,
    (event_f) blockchain_forward,
    (revent_f) blockchain_reverse,
    (commit_f) blockchain_commit,
    (final_f) blockchain_final,
    (map_f) metis_map,
    sizeof(blockchain)
  }
};

// Define Model-level data sampling
st_model_types model_types[] = {
  {
    (ev_trace_f) event_trace,
    (size_t) sizeof(event_model_data),
    (model_stat_f) NULL,
    (size_t) 0,
    (sample_event_f) NULL,
    (sample_revent_f) NULL,
    (size_t) 0
  },
  {0}
};

//add your command line opts
const tw_optdef model_opts[] = {
  TWOPT_GROUP("Itcoin PCN Model"),
  TWOPT_CHAR("input-dir", input_dir_name, "Input directory with topologies"),
  TWOPT_CHAR("output-dir", output_dir_name, "Output directory to store CLoTH results"),
  TWOPT_UINT("use-known-paths", use_known_paths, "Read known paths from the input directory. If not, paths are calculated during the simulation time."),
  TWOPT_UINT("tps", tx_per_second, "Global network-wide transactions per second to generate"),
  TWOPT_CHAR("tps-cfg", tps_cfg_file, "Configuration file for shaping the transaction generator. If given, overrides --tps"),
  TWOPT_UINT("waterfall", waterfall_enabled, "Enables automatic deposits to custodians"),
  TWOPT_UINT("reverse-waterfall", rev_waterfall_enabled, "Enables automatic withdrawals from custodians"),
  TWOPT_UINT("submarine-swaps", submarine_swaps_enabled, "Enables liquidity swaps between LSPs"),
  TWOPT_DOUBLE("submarine-swap-threshold", submarine_swap_threshold, "The balance threshold that triggers the submarine swap in percentage of the channel capacity"),
  TWOPT_UINT("block-size", block_size, "The block size of the blockchain"),
  TWOPT_UINT("block-time", block_time, "The block time of the blockchain"),
  TWOPT_DOUBLE("block-congestion-rate", block_congestion_rate, "The block congestion rate, where 0.0 means empty block and 1.0 means full blocks"),
  TWOPT_END(),
};


//for doxygen
#define model_main main


int model_main (int argc, char* argv[]) {
	tw_opt_add(model_opts);
	tw_init(&argc, &argv);

  //Do some error checking
  // Simulations cannot last more than 1 week
  if(g_tw_ts_end>=1e10){
    printf("The simulation time exeeds max value allowed in payment ids. %2.3f>=1e10\n", g_tw_ts_end);
    exit(-1);
  }

  if (submarine_swap_threshold <= 0.5 || submarine_swap_threshold > 1){
    printf("submarine_swap_threshold must be 0.5 < <= 1, is: %2.3f\n", submarine_swap_threshold);
    exit(-1);
  }

  if(strlen(output_dir_name)>PATH_MAX-101){
    printf("output_dir_name is too long, exiting");
    exit(-1);
  }

  //Print out some settings
  printf("SIMULATION PARAMETERS:\n");
  if (strcmp(tps_cfg_file, "") == 0) {
    printf("tps (Global network-wide transactions per second to generate):  %u\n", tx_per_second);
  } else {
    printf("tps-cfg (Configuration file for the transaction generator: %s\n", tps_cfg_file);
  }
  printf("input-dir: %s\n", input_dir_name);
  printf("output-dir: %s\n", output_dir_name);


  //Useful ROSS variables and functions
  // tw_nnodes() : number of nodes/processors defined
  // g_tw_mynode : my node/processor id (mpi rank)

  //Useful ROSS variables (set from command line)
  // g_tw_events_per_pe
  // g_tw_lookahead
  // g_tw_nlp
  // g_tw_nkp
  // g_tw_synchronization_protocol

	// Do some file I/O here? on a per-node (not per-LP) basis
  // Initialize network and partitions.
  if (g_tw_synchronization_protocol==SEQUENTIAL){
    // Force all partitions to 0 if execution is SEQUENTIAL
    printf("WARNING: Executing a SEQUENTIAL simulation, all nodes will be on the same partition, independently of their partition value.\n");
	  network = initialize_network(input_dir_name, use_known_paths, 1);
  }
  else {
    network = initialize_network(input_dir_name, use_known_paths, 0);
  }

  // Simulations cannot have more than 9.99e9 users
  if(array_len(network->nodes)>=1e10){
    printf("The number of users exeeds max value allowed in payment ids. %ld>=1e10\n", array_len(network->nodes));
    exit(-1);
  }

  // Initialize routing
  initialize_routing(&global_router_state, path_table, network, input_dir_name, use_known_paths);

  // Define the custom Mapping
  g_tw_mapping = CUSTOM;
  g_tw_custom_initial_mapping = &metis_custom_mapping;
  g_tw_custom_lp_global_to_local_map = &metis_mapping_to_lp;

  // The blockchain lp global id is the number of users
  blockchain_lp_gid = array_len(network->nodes);

  //set up LPs within ROSS
  nlp_user_per_pe = list_len(array_get(network->partitions, g_tw_mynode));
	int num_lps_per_pe = g_tw_mynode != 0 ? nlp_user_per_pe : nlp_user_per_pe + 1; // node0 gets the blockchain LP
	tw_define_lps(num_lps_per_pe, sizeof(struct message));
	// note that g_tw_nlp gets set here by tw_define_lps

  // IF there are multiple LP types
  //    you should define the mapping of GID -> lptype index
  //g_tw_lp_typemap = &model_typemap;

  // set the global variable and initialize each LP's type
  //g_tw_lp_types = model_lps;
  //tw_lp_setup_types();

  // Output file settings
  char debugfilename[PATH_MAX];
  sprintf(debugfilename, "%s/node_logs_file_%ld.txt", output_dir_name, g_tw_mynode);
  node_out_file = fopen(debugfilename,"w");

  // Initialize the list of payments
  node_payments_array = array_initialize(2e6);

  // Initialize node indexes
  init_node_indexes_per_pe();

  // Initialize transaction generator data structs
  init_tx_generator_state_per_pe();

  tw_run();

  fclose(node_out_file);

  tw_end();

  return 0;
}
