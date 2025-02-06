#ifndef _message_h
#define _message_h

#include <ross.h>

typedef enum event_type {
  FINDPATH,
  SENDPAYMENT,
  FORWARDPAYMENT,
  RECEIVEPAYMENT,
  FORWARDSUCCESS,
  FORWARDFAIL,
  RECEIVESUCCESS,
  RECEIVEFAIL,
  OPENCHANNEL,

  // Generate payments
  GENERATE_PAYMENT,

  // Waterfall functionality
  NOTIFYPAYMENT,

  // Submarine swaps functionality
  SWAP_REQUEST,

  // Blockchain events type
  BC_TX_BROADCAST,
  BC_TX_CONFIRMED,
  TICK_TOCK_NEXT_BLOCK
} event_type;

//Message struct
//   this contains all data sent in an event
#define MAX_SERIALIZED_LENGTH 1024

struct message {
  // Message type and serialized data
  event_type type;
  char data[MAX_SERIALIZED_LENGTH];

  // One field for each possible deserialized data type
  struct payment* payment;
  struct blockchain_tx* tx;
  struct submarine_swap* swap;

  // Simulator utilities
  unsigned long rng_count;
  tw_stime fwd_handler_time;
  double computation_time;
};

const char* getEventName(event_type event);

#endif
