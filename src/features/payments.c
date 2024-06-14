#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdint.h>
#include <math.h>
#include <inttypes.h>

#include "../utils/array.h"
#include "htlc.h"
#include "payments.h"
#include "network.h"
#include "routing.h"

#include "../model/global.h"
#include "../model/message.h"

/* Functions in this file generate the payments that are exchanged in the payment-channel network during the simulation */


struct payment* new_payment(long sender, long receiver, uint64_t amount, uint64_t start_time, enum payment_type type) {
  struct payment * p;
  p = malloc(sizeof(struct payment));
  init_payment(p, sender, receiver, amount, start_time, type);
  return p;
}

void init_payment(struct payment* p, long sender, long receiver, uint64_t amount, uint64_t start_time, enum payment_type type) {
  long id = 1e9*sender + start_time;
  p->id=id;
  p->sender= sender;
  p->receiver = receiver;
  p->amount = amount;
  p->start_time = start_time;
  p->last_hop_id = -1;
  p->route = NULL;
  p->is_success = 0;
  p->offline_node_count = 0;
  p->no_balance_count = 0;
  p->is_timeout = 0;
  p->end_time = 0;
  p->attempts = 0;
  p->error.type = NOERROR;
  p->error.hop = NULL;
  p->is_shard = 0;
  p->shards_id[0] = p->shards_id[1] = -1;
  p->type = type;
}

void free_payment(struct payment* payment){
  if(payment->route!=NULL){
    array_free(payment->route->route_hops);
    payment->route->route_hops=NULL;
  }
  free(payment->route);
  payment->route=NULL;
  free(payment);
  payment=NULL;
}

int is_expired_payment(const struct payment* payment, uint64_t current_time){
  // We assume that SUBMARINE_SWAP expire after 10*block_time
  if (payment->type == SUBMARINE_SWAP && current_time > payment->start_time + 10*block_time) {
    return 1;
  }
  // Other payments expire after payments_expire_after_ms
  else if (payment->type != SUBMARINE_SWAP && current_time > payment->start_time + payments_expire_after_ms)
    return 1;
  else
    return 0;
}

void set_expired_payment(struct payment* payment, uint64_t current_time){
  payment->end_time = current_time;
  payment->is_timeout = 1;
}

void serialize_payment(payment* payment, char* serialized){
    if (!payment || !serialized) {
        return; // Invalid input or insufficient buffer size
    }

    char* current_pos = serialized + sizeof(size_t); // leave space for the size at the beginning

    // Serialize the payment
    if (payment != NULL) {
        // Serialize payment fields
        memcpy(current_pos, &payment->id, sizeof(payment->id));
        current_pos += sizeof(payment->id);

        memcpy(current_pos, &payment->sender, sizeof(payment->sender));
        current_pos += sizeof(payment->sender);

        memcpy(current_pos, &payment->receiver, sizeof(payment->receiver));
        current_pos += sizeof(payment->receiver);

        memcpy(current_pos, &payment->amount, sizeof(payment->amount));
        current_pos += sizeof(payment->amount);

        memcpy(current_pos, &payment->last_hop_id, sizeof(payment->last_hop_id));
        current_pos += sizeof(payment->last_hop_id);

        memcpy(current_pos, &payment->start_time, sizeof(payment->start_time));
        current_pos += sizeof(payment->start_time);

        memcpy(current_pos, &payment->end_time, sizeof(payment->end_time));
        current_pos += sizeof(payment->end_time);

        memcpy(current_pos, &payment->attempts, sizeof(payment->attempts));
        current_pos += sizeof(payment->attempts);

        memcpy(current_pos, &payment->is_shard, sizeof(payment->is_shard));
        current_pos += sizeof(payment->is_shard);

        memcpy(current_pos, &payment->shards_id[0], sizeof(payment->shards_id[0]));
        current_pos += sizeof(payment->shards_id[0]);

        memcpy(current_pos, &payment->shards_id[1], sizeof(payment->shards_id[1]));
        current_pos += sizeof(payment->shards_id[1]);

        memcpy(current_pos, &payment->is_success, sizeof(payment->is_success));
        current_pos += sizeof(payment->is_success);

        memcpy(current_pos, &payment->offline_node_count, sizeof(payment->offline_node_count));
        current_pos += sizeof(payment->offline_node_count);

        memcpy(current_pos, &payment->no_balance_count, sizeof(payment->no_balance_count));
        current_pos += sizeof(payment->no_balance_count);

        memcpy(current_pos, &payment->is_timeout, sizeof(payment->is_timeout));
        current_pos += sizeof(payment->is_timeout);

        memcpy(current_pos, &payment->type, sizeof(payment->type));
        current_pos += sizeof(payment->type);

        // Serialize the payment error...
        memcpy(current_pos, &payment->error.type, sizeof(payment->error.type));
        current_pos += sizeof(payment->error.type);

        memcpy(current_pos, &payment->error.time, sizeof(payment->error.time));
        current_pos += sizeof(payment->error.time);

        memcpy(current_pos, &payment->error.hop, sizeof(payment->error.hop));
        current_pos += sizeof(payment->error.hop);

        if (payment->error.hop != NULL) {
            // Serialize the route_hop
            memcpy(current_pos, &payment->error.hop->from_node_id, sizeof(payment->error.hop->from_node_id));
            current_pos += sizeof(payment->error.hop->from_node_id);

            memcpy(current_pos, &payment->error.hop->to_node_id, sizeof(payment->error.hop->to_node_id));
            current_pos += sizeof(payment->error.hop->to_node_id);

            memcpy(current_pos, &payment->error.hop->edge_id, sizeof(payment->error.hop->edge_id));
            current_pos += sizeof(payment->error.hop->edge_id);

            memcpy(current_pos, &payment->error.hop->amount_to_forward, sizeof(payment->error.hop->amount_to_forward));
            current_pos += sizeof(payment->error.hop->amount_to_forward);

            memcpy(current_pos, &payment->error.hop->timelock, sizeof(payment->error.hop->timelock));
            current_pos += sizeof(payment->error.hop->timelock);
        }

        // Serialize the route...
        memcpy(current_pos, &payment->route, sizeof(payment->route));
        current_pos += sizeof(payment->route);
        if (payment->route != NULL) {
            // Serialize route fields
            memcpy(current_pos, &payment->route->total_amount, sizeof(payment->route->total_amount));
            current_pos += sizeof(payment->route->total_amount);

            memcpy(current_pos, &payment->route->total_fee, sizeof(payment->route->total_fee));
            current_pos += sizeof(payment->route->total_fee);

            memcpy(current_pos, &payment->route->total_timelock, sizeof(payment->route->total_timelock));
            current_pos += sizeof(payment->route->total_timelock);

            memcpy(current_pos, &payment->route->route_hops, sizeof(payment->route->route_hops));
            current_pos += sizeof(payment->route->route_hops);

            if (payment->route->route_hops != NULL) {
                // Serialize route_hops array elements
                memcpy(current_pos, &payment->route->route_hops->index, sizeof(payment->route->route_hops->index));
                current_pos += sizeof(payment->route->route_hops->index);
                for (long i = 0; i < payment->route->route_hops->index; i++) {
                    // Serialize each route_hop
                    memcpy(current_pos, array_get(payment->route->route_hops, i), sizeof(struct route_hop));
                    current_pos += sizeof(struct route_hop);
                }
            }
        }
    }

    // Calculate the total size of the serialized string
    size_t serialized_size = current_pos - serialized;

    // Ensure that the serialized string doesn't exceed the maximum length
    if (serialized_size > MAX_SERIALIZED_LENGTH) {
        return; // Serialization exceeded the maximum length
    }

    // Add the serialized string size at the beginning
    memcpy(serialized, &serialized_size, sizeof(serialized_size));

    // Pad the remaining space with zeros
    size_t padding_size = MAX_SERIALIZED_LENGTH - serialized_size;
    if (padding_size > 0) {
        memset(serialized + serialized_size, 0, padding_size);
    }
}

payment* deserialize_payment(const char* serialized){

    payment* payment;
    size_t payment_size = 0;

    const char *current_pos = serialized;

    // Read the size of the serialized data
    memcpy(&payment_size, current_pos, sizeof(payment_size));
    current_pos += sizeof(payment_size);

    // Allocate memory for the payment structure
    payment = malloc(sizeof(struct payment));

    // Read payment fields
    memcpy(&payment->id, current_pos, sizeof(payment->id));
    current_pos += sizeof(payment->id);

    memcpy(&payment->sender, current_pos, sizeof(payment->sender));
    current_pos += sizeof(payment->sender);

    memcpy(&payment->receiver, current_pos, sizeof(payment->receiver));
    current_pos += sizeof(payment->receiver);

    memcpy(&payment->amount, current_pos, sizeof(payment->amount));
    current_pos += sizeof(payment->amount);

    memcpy(&payment->last_hop_id, current_pos, sizeof(payment->last_hop_id));
    current_pos += sizeof(payment->last_hop_id);

    memcpy(&payment->start_time, current_pos, sizeof(payment->start_time));
    current_pos += sizeof(payment->start_time);

    memcpy(&payment->end_time, current_pos, sizeof(payment->end_time));
    current_pos += sizeof(payment->end_time);

    memcpy(&payment->attempts, current_pos, sizeof(payment->attempts));
    current_pos += sizeof(payment->attempts);

    memcpy(&payment->is_shard, current_pos, sizeof(payment->is_shard));
    current_pos += sizeof(payment->is_shard);

    memcpy(&payment->shards_id[0], current_pos, sizeof(payment->shards_id[0]));
    current_pos += sizeof(payment->shards_id[0]);

    memcpy(&payment->shards_id[1], current_pos, sizeof(payment->shards_id[1]));
    current_pos += sizeof(payment->shards_id[1]);

    memcpy(&payment->is_success, current_pos, sizeof(payment->is_success));
    current_pos += sizeof(payment->is_success);

    memcpy(&payment->offline_node_count, current_pos, sizeof(payment->offline_node_count));
    current_pos += sizeof(payment->offline_node_count);

    memcpy(&payment->no_balance_count, current_pos, sizeof(payment->no_balance_count));
    current_pos += sizeof(payment->no_balance_count);

    memcpy(&payment->is_timeout, current_pos, sizeof(payment->is_timeout));
    current_pos += sizeof(payment->is_timeout);

    memcpy(&payment->type, current_pos, sizeof(payment->type));
    current_pos += sizeof(payment->type);

    // Read payment error
    memcpy(&payment->error.type, current_pos, sizeof(payment->error.type));
    current_pos += sizeof(payment->error.type);

    memcpy(&payment->error.time, current_pos, sizeof(payment->error.time));
    current_pos += sizeof(payment->error.time);

    // Read payment error hop
    memcpy(&payment->error.hop, current_pos, sizeof(payment->error.hop));
    current_pos += sizeof(payment->error.hop);

    if (payment->error.hop != NULL) {
        // Allocate memory for the error hop
        payment->error.hop = (struct route_hop *)malloc(sizeof(struct route_hop));

        memcpy(&payment->error.hop->from_node_id, current_pos, sizeof(payment->error.hop->from_node_id));
        current_pos += sizeof(payment->error.hop->from_node_id);

        memcpy(&payment->error.hop->to_node_id, current_pos, sizeof(payment->error.hop->to_node_id));
        current_pos += sizeof(payment->error.hop->to_node_id);

        memcpy(&payment->error.hop->edge_id, current_pos, sizeof(payment->error.hop->edge_id));
        current_pos += sizeof(payment->error.hop->edge_id);

        memcpy(&payment->error.hop->amount_to_forward, current_pos, sizeof(payment->error.hop->amount_to_forward));
        current_pos += sizeof(payment->error.hop->amount_to_forward);

        memcpy(&payment->error.hop->timelock, current_pos, sizeof(payment->error.hop->timelock));
        current_pos += sizeof(payment->error.hop->timelock);
    }

    // Read the route
    memcpy(&payment->route, current_pos, sizeof(payment->route));
    current_pos += sizeof(payment->route);

    if (payment->route != NULL) {
        // Allocate memory for the route structure
        payment->route = (struct route *)malloc(sizeof(struct route));
        // Read route fields
        memcpy(&payment->route->total_amount, current_pos, sizeof(payment->route->total_amount));
        current_pos += sizeof(payment->route->total_amount);

        memcpy(&payment->route->total_fee, current_pos, sizeof(payment->route->total_fee));
        current_pos += sizeof(payment->route->total_fee);

        memcpy(&payment->route->total_timelock, current_pos, sizeof(payment->route->total_timelock));
        current_pos += sizeof(payment->route->total_timelock);

        memcpy(&payment->route->route_hops, current_pos, sizeof(payment->route->route_hops));
        current_pos += sizeof(payment->route->route_hops);

        if (payment->route->route_hops != NULL){
            // Read route_hops array
            long hops_array_size;
            memcpy(&hops_array_size, current_pos, sizeof(hops_array_size));
            current_pos += sizeof(hops_array_size);

            // Initialize the route_hops array
            payment->route->route_hops = array_initialize(hops_array_size);

            // Read and insert route_hop elements
            for (long i = 0; i < hops_array_size; i++) {
                struct route_hop *r = (struct route_hop *)malloc(sizeof(struct route_hop));

                // Read route_hop fields
                memcpy(r, current_pos, sizeof(struct route_hop));
                current_pos += sizeof(struct route_hop);

                // Insert the route_hop into the route_hops array
                array_insert(payment->route->route_hops, r);
            }
        }
    }

    // Verify that the remaining evt_size is 0
    if (current_pos - serialized - sizeof(size_t) != 0) {
        // Handle deserialization error (unexpected data size)
    }

    // Return the deserialized payment
    return payment;
}
