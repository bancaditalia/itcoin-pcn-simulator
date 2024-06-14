#ifndef model_extern_h
#define model_extern_h

// https://stackoverflow.com/questions/73168335/difference-between-include-limits-h-and-inlcude-linux-limits-h
#include <linux/limits.h>
#include <stdio.h>
#include <ross.h>

#include "../utils/hash_table.h"

extern struct network *network;

// Helper structs for routing
extern struct router_state global_router_state;

/*
 * Controlled by:
 * - the "--waterfall" command line parameter;
 * - the "--reverse-waterfall" command line parameter;
 * - the "--submarine-swaps" command line parameter;
 *
 * Automatic deposits (waterfall), automatic withdrawals (reverse-waterfall)
 * and on-chain vs off-chain atomic swaps (submarine-swaps)
 *
 * Default value: 1 (defined in global.c)
 */
extern unsigned int waterfall_enabled;
extern unsigned int rev_waterfall_enabled;
extern unsigned int submarine_swaps_enabled;

/*
 * Controlled by the "--tps" command line parameter.
 *
 * If this parameter is given (and "--tps-cfg" is not given or is empty), the
 * load generator works in constant load mode, and generates a constant load of
 * "--tps" transactions per second across the whole simulation.
 *
 * Default value: 20 (defined in global.c)
 */
extern unsigned int tx_per_second;

/*
 * Controlled by the "--tps-cfg" command line parameter.
 *
 * Path to a configuration file that, if different from "", switches the tx
 * generator mode: instead of a constant load controlled by the "--tps"
 * parameter, the load is variable, according to the law described in the given
 * configuration file.
 *
 * The simulation time is divided in TPS_CFG_MAX_ROWS (currently 96) intervals
 * and a constant load is generated for each interval. The duration of each
 * interval is therefore variable. For a 24 hours simulation each interval will
 * last 15 minutes (24 h / 96).
 *
 * Default value: "" (defined in global.c), means that no configuration
 *                file will be read, and the load will be constant and
 *                controlled by "--tps".
 */
extern char tps_cfg_file[PATH_MAX];

/*
 * The payment timeout in milliseconds
 * Default value: 10000 (defined in global.c)
 */
extern unsigned int payments_expire_after_ms;

/*
 * The time it takes for a node to find a routet in milliseconds
 * Default value: 500 (defined in global.c)
 */
extern unsigned int ROUTING_LATENCY;

// Network propagation delay parameters
extern double DELAY_GAMMA_DISTR_ALPHA;
extern double DELAY_GAMMA_DISTR_BETA;

/*
 * The submarine swap threshold in percentage of the channel capacity
 * Default value: 0.9 (defined in global.c)
 */
extern double submarine_swap_threshold;

extern char input_dir_name[PATH_MAX];
extern char output_dir_name[PATH_MAX-100];

/*
 * Controlled by the "--use-known-paths" command line parameter;
 * If 1, it reads known paths from the input directory. If 0, then paths are calculated during the simulation time.
 * Default value: 1 (defined in global.c)
 */
extern unsigned int use_known_paths;

// global file pointer to logs
extern FILE* node_out_file;
// All the payments processed by this node, to be saved to output
extern struct array* node_payments_array;

// Number of LP of type user/node per physical elements
extern int nlp_user_per_pe;

//
extern struct hash_table *path_table[TABLE_SIZE];

// The global LP id of the blockchain
extern tw_lpid blockchain_lp_gid;

/*
 * The block size, the maximum number of transactions that are included in a block
 * Default value: 4 (defined in global.c)
 */
extern unsigned int block_size;

/*
 * The blockchain block time
 * Default value: 60000 (defined in global.c)
 */
extern unsigned int block_time;

/*
 * The block congestion rate, 0.0 means empty block, 1.0 means full blocks
 * Default value: 0 (defined in global.c)
 */
extern double block_congestion_rate;

// Used for debugging
extern int g_dbg_trace;

extern struct tx_generator_state g_pe_tx_generator_state;

#endif
