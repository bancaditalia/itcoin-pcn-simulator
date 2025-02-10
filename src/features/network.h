#ifndef NETWORK_H
#define NETWORK_H

#include <stdio.h>
#include <stdint.h>

#define MAXMSATOSHI 5E17 //5 millions  bitcoin
#define MAXTIMELOCK 100
#define MINTIMELOCK 10
#define MAXFEEBASE 5000
#define MINFEEBASE 1000
#define MAXFEEPROP 10
#define MINFEEPROP 1
#define MAXLATENCY 100
#define MINLATENCY 10
#define MINBALANCE 1E2
#define MAXBALANCE 1E11
#define MAXNODELABELSIZE 30

#define COUNTRYLABELSIZE 3 // 2+\0
#define NUM_COUNTRIES 21

// Information needed to read a network from file
struct network_params{
  char nodes_filename[256];
  char channels_filename[256];
  char edges_filename[256];
  char network_filename[256];
};

/* a policy that must be respected when forwarding a payment through an edge (see edge below) */
struct policy {
  uint64_t fee_base;
  uint64_t fee_proportional;
  uint64_t min_htlc;
  uint32_t timelock;
};

enum node_type {
  END_USER,
  MERCHANT,
  INTERMEDIARY,
  CB
};

enum node_size {
  SMALL,
  MEDIUM,
  BIG
};

enum node_country {
  AT,
  BE,
  CY,
  DE,
  EE,
  ES,
  FI,
  FR,
  GR,
  HR,
  IE,
  IT,
  LT,
  LU,
  LV,
  MT,
  NL,
  PT,
  SI,
  SK,
  EU,
};

struct node_list_element {
    long from_node_id;
    struct element* edges;
};

/* a node of the payment-channel network */
struct node {
  long id;
  char* label;
  long intermediary;
  struct array* open_edges;
  struct element *results;
  unsigned int explored;
  enum node_type type;
  enum node_size size;
  enum node_country country;
  int partition;
  int local_id;

  // Reverse waterfall, the pending payment and the withdrwawal id
  struct payment* rw_awaiting_payment;
  long rw_withdrawal_id;
  // Pending submarine swaps
  struct array* submarine_swaps;
};

/* a bidirectional payment channel of the payment-channel network open between two nodes */
struct channel {
  long id;
  long node1;
  long node2;
  long edge1;
  long edge2;
  uint64_t capacity;
  unsigned int is_closed;
  unsigned int is_private;
};

/* an edge represents one of the two direction of a payment channel */
struct edge {
  long id;
  long channel_id;
  long from_node_id;
  long to_node_id;
  long counter_edge_id;
  struct policy policy;
  uint64_t balance;
  unsigned int is_closed;
  uint64_t tot_flows;
};


struct graph_channel {
  long node1_id;
  long node2_id;
};


struct network {
  struct array* nodes;
  struct array* channels;
  struct array* edges;
  struct array* partitions;
};

struct node* new_node(long id, char* label, enum node_type type,enum node_size node_size, enum node_country node_country);

struct channel* new_channel(long id, long direction1, long direction2, long node1, long node2, uint64_t capacity, unsigned int is_private);

struct edge* new_edge(long id, long channel_id, long counter_edge_id, long from_node_id, long to_node_id, uint64_t balance, struct policy policy);

struct network* initialize_network(char input_dir_name[], unsigned int use_known_paths, int force_single_partition);

void free_network(struct network* network);

uint64_t get_node_available_balance(struct node* node);

uint64_t get_node_wallet_cap(struct network* network, struct node* node);

#endif
