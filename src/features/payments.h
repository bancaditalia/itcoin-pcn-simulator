#ifndef PAYMENTS_H
#define PAYMENTS_H

#include <stdint.h>

enum payment_error_type{
  NOERROR,
  NOBALANCE,
  OFFLINENODE, //it corresponds to `FailUnknownNextPeer` in lnd
  NOCAPACITY // When a PATH can't be found
};

enum payment_type{
  TX,
  DEPOSIT,
  WITHDRAWAL,
  SUBMARINE_SWAP
};

/* register an eventual error occurred when the payment traversed a hop */
struct payment_error{
  enum payment_error_type type;
  struct route_hop* hop;
  uint64_t time;
};

struct payment {
  long id;
  long sender;
  long receiver;
  uint64_t amount; //millisatoshis
  /* attribute for creating a route with private channels (mimics the r tagged field in bolt11 invoice)*/
  long last_hop_id; // -1 is the default, means absence of last_hop_id
  struct route* route;
  uint64_t start_time;
  uint64_t end_time;
  int attempts;
  struct payment_error error;
  /* attributes for multi-path-payment (mpp)*/
  unsigned int is_shard;
  long shards_id[2];
  /* attributes used for computing stats */
  unsigned int is_success;
  int offline_node_count;
  int no_balance_count;
  unsigned int is_timeout;
  enum payment_type type;
};

struct payment* new_payment(long sender, long receiver, uint64_t amount, uint64_t start_time, enum payment_type type);
void init_payment(struct payment* p, long sender, long receiver, uint64_t amount, uint64_t start_time, enum payment_type type);
void free_payment(struct payment* payment);
int is_expired_payment(const struct payment* payment, uint64_t current_time);
void set_expired_payment(struct payment* payment, uint64_t current_time);

// Serialization and deserialization functions
void serialize_payment(struct payment* payment, char* serialized);
struct payment* deserialize_payment(const char* serialized);

#endif
