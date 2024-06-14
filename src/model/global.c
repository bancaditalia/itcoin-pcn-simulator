#include "global.h"

#include "../features/routing.h"

struct network *network;
unsigned int waterfall_enabled = 1;
unsigned int rev_waterfall_enabled = 1;
unsigned int submarine_swaps_enabled = 1;

char tps_cfg_file[PATH_MAX] = ""; // empty by default: the load generator will operate in constant load mode
char input_dir_name[PATH_MAX] = "./data_in";
char output_dir_name[PATH_MAX-100] = "./data_out";
unsigned int use_known_paths = 1;
FILE* node_out_file;
struct array* node_payments_array;
int nlp_user_per_pe;
struct hash_table *path_table[TABLE_SIZE];

// Payments constants
unsigned int payments_expire_after_ms = 10000;

// Load generation
unsigned int tx_per_second = 20;

// Network Delays
unsigned int ROUTING_LATENCY = 500;
double DELAY_GAMMA_DISTR_ALPHA = 6.40;
double DELAY_GAMMA_DISTR_BETA = 4.35;

// Blockchain related parameters
tw_lpid blockchain_lp_gid;
unsigned int block_size = 4;
unsigned int block_time = 60000;
double block_congestion_rate = 0.0;

// Submarine swaps
double submarine_swap_threshold = 0.9;

// Helper structs for routing
struct router_state global_router_state = {
  .n_find_path = 0,
  .distance = NULL,
  .distance_heap = NULL,
  .rollback_count = 0
};
