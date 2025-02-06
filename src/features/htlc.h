#ifndef HTLC_H
#define HTLC_H

#include <stdint.h>

#include <ross.h>

#include "routing.h"

#define OFFLINELATENCY 3000 //3 seconds waiting for a node not responding (tcp default retransmission time)


struct edge;
struct payment;
struct policy;

/* a node pair result registers the most recent result of a payment (fail or success, with the corresponding amount and time)
   that occurred when the payment traversed an edge connecting the two nodes of the node pair */
struct node_pair_result{
  long to_node_id;
  uint64_t fail_time;
  uint64_t fail_amount;
  uint64_t success_time;
  uint64_t success_amount;
};


uint64_t compute_fee(uint64_t amount_to_forward, struct policy policy);

struct array * find_path(struct router_state *router_state, struct payment *payment, uint64_t current_time, struct network* network);

int send_payment(tw_lp *lp, struct payment* payment);

int forward_payment(tw_lp *lp, struct payment* payment);

void receive_payment(tw_lp *lp, struct payment* payment);

void forward_success(tw_lp *lp, struct payment* payment);

void receive_success(tw_lp *lp, struct payment* payment);

void forward_fail(tw_lp *lp, struct payment* payment);

void receive_fail(tw_lp *lp, struct payment* payment);

struct route_hop *get_route_hop(long node_id, struct array *route_hops, int is_sender);

unsigned int check_balance_and_policy(struct edge* edge, struct edge* prev_edge, struct route_hop* prev_hop, struct route_hop* next_hop);

void process_success_result(struct node* node, struct payment *payment, uint64_t current_time);

void process_fail_result(struct node* node, struct payment *payment, uint64_t current_time);

void notify_payment(tw_lp *lp, struct payment* payment);

void rev_send_payment(tw_lp *lp, struct payment* payment);
void rev_forward_payment(tw_lp *lp, struct payment* payment);
void rev_receive_payment(tw_lp *lp, struct payment* payment);
void rev_forward_success(tw_lp *lp, struct payment* payment);
void rev_receive_success(tw_lp *lp, struct payment* payment);
void rev_forward_fail(tw_lp *lp, struct payment* payment);
void rev_receive_fail(tw_lp *lp, struct payment* payment);
void rev_notify_payment(tw_lp *lp, struct payment* payment);

#endif
