#ifndef ROUTING_H
#define ROUTING_H

#include <stdint.h>
#include <pthread.h>
#include "network.h"
#include "payments.h"
#include "../utils/array.h"
#include "../utils/hash_table.h"

#define FINALTIMELOCK 40


struct distance{
  long node;
  uint64_t distance;
  uint64_t amt_to_receive;
  uint64_t fee;
  double probability;
  uint32_t timelock;
  double weight;
  long next_edge;
};

struct dijkstra_hop {
  long node;
  long edge;
};

struct path_hop{
  long sender;
  long receiver;
  long edge;
};

struct route_hop {
  long from_node_id;
  long to_node_id;
  long edge_id;
  uint64_t amount_to_forward;
  uint32_t timelock;
};


struct route {
  uint64_t total_amount;
  uint64_t total_fee;
  uint64_t total_timelock;
  struct array *route_hops;
};

enum pathfind_error{
  NOLOCALBALANCE,
  NOPATH
};

typedef struct router_state{
    int n_find_path;
    struct distance* distance;
    struct heap* distance_heap;
    int rollback_count;
} router_state;

void get_balance(struct node* node, uint64_t *max_balance, uint64_t *total_balance);

struct array* dijkstra(router_state *router_state, long source, long target, long last_hop_id, uint64_t amount, struct network* network, uint64_t current_time, enum pathfind_error *error);

void generate_payment_route(struct payment* payment, struct array* path, struct network* network);

struct route* transform_path_into_route(struct array* path_hops, uint64_t amount_to_send, struct network* network);

void print_hop(struct route_hop* hop);

int compare_distance(struct distance* a, struct distance* b);

double millisec_to_hour(double time);

double get_weight(double age);

double get_node_probability(struct element* node_results, uint64_t amount, uint64_t current_time);

double calculate_probability(struct element* node_results, long to_node_id, uint64_t amount, double node_probability, uint64_t current_time);

double get_probability(long from_node_id, long to_node_id, uint64_t amount, long sender_id, uint64_t current_time,  struct network* network);

uint64_t get_probability_based_dist(double weight, double probability);

double get_edge_weight(uint64_t amount, uint64_t fee, uint32_t timelock);

void initialize_routing(
  struct router_state* global_router_state, struct hash_table* path_table[],
  const struct network* network, char input_dir_name[], unsigned int use_known_paths);

#endif
