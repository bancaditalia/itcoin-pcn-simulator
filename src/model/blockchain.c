#include "blockchain.h"

#include <dirent.h>
#include <ross.h>
#include <stdlib.h>
#include <string.h>
#include "../utils/logging.h"
#include "../utils/array.h"

#include "../model/message.h"

#include "global.h"

const char* getTxType(blockchain_tx_type type){
  switch(type){
    case PREPARE_HTLC: return      "PREPARE_HTLC";
    case CLAIM_HTLC: return        "CLAIM_HTLC  ";
  }
}

/* Utilities functions */
void tick_tock_next_block(tw_lp *sender_lp){
  // Create a new TICK_TOCK_NEXT_BLOCK message to myself
  tw_stime next_block_time_offset = round(tw_rand_exponential(sender_lp->rng, (double) block_time));
  tw_event *first_block_event = tw_event_new(blockchain_lp_gid, next_block_time_offset, sender_lp);
  struct message *first_block_msg = tw_event_data(first_block_event);
  first_block_msg->type = TICK_TOCK_NEXT_BLOCK;
  memset(&first_block_msg->data[0], 0, sizeof(first_block_msg->data));
  tw_event_send(first_block_event);
}

void blockchain_init(struct blockchain *s, tw_lp *lp) {
  s->mempool = array_initialize(10*block_size);
  s->blocks = array_initialize(100);
  tick_tock_next_block(lp);
}

void blockchain_forward(struct blockchain *s, tw_bf *bf, struct message *in_msg, tw_lp *lp) {
  tw_clock start_time = tw_clock_read();
  in_msg->fwd_handler_time = tw_now(lp);
  long rng_start_count = lp->rng->count;

  switch (in_msg->type) {
    case TICK_TOCK_NEXT_BLOCK:
      // Print debug line
      debug_blockchain_forward(node_out_file, lp, in_msg);

      // Allocate the block
      struct block* next_block = malloc(sizeof(struct block));
      next_block->confirmation_time = tw_now(lp);
      next_block->transactions = array_initialize(block_size);

      // Available block size depends on the congestion rate
      int block_period = 100;
      int transactions_in_period = block_period * block_size;
      int available_transactions_in_period = transactions_in_period * (1.0 - block_congestion_rate);
      int transactions_x_block_int = available_transactions_in_period / block_period;
      int transactions_x_block_rem = available_transactions_in_period % block_period;
      int next_block_number = array_len(s->blocks);
      int next_block_number_in_period = next_block_number % block_period;
      int available_block_size = transactions_x_block_int + 1*(next_block_number_in_period<transactions_x_block_rem);

      // Take transactions from the mempool, add them to block
      while(array_len(s->mempool) && array_len(next_block->transactions)<available_block_size) {
        // Get the first transaction from the mempool
        struct blockchain_tx* tx = array_get(s->mempool, 0);

        // Delete transaction from the mempool
        array_delete_element_nofree(s->mempool, 0);

        // Add transaction to the block
        next_block->transactions = array_insert(next_block->transactions, tx);

        // Notify lps involved in the block transactions about the block
        // Notify the sender
        tw_event *sender_e = tw_event_new(tx->sender, tw_rand_gamma(lp->rng, DELAY_GAMMA_DISTR_ALPHA, DELAY_GAMMA_DISTR_BETA), lp);
        struct message *sender_msg = tw_event_data(sender_e);
        sender_msg->type = BC_TX_CONFIRMED;
        serialize_blockchain_tx(tx, sender_msg->data);
        tw_event_send(sender_e);

        // Notify the receiver
        tw_event *rcvr_e = tw_event_new(tx->receiver, tw_rand_gamma(lp->rng, DELAY_GAMMA_DISTR_ALPHA, DELAY_GAMMA_DISTR_BETA), lp);
        struct message *rcvr_msg = tw_event_data(rcvr_e);
        rcvr_msg->type = BC_TX_CONFIRMED;
        serialize_blockchain_tx(tx, rcvr_msg->data);
        tw_event_send(rcvr_e);
      }

      // Save the block in the blockchain
      s->blocks = array_insert(s->blocks, next_block);

      // Start the time to create a new block
      tick_tock_next_block(lp);
      break;
    case BC_TX_BROADCAST:
      in_msg->tx = deserialize_blockchain_tx(in_msg->data);
      // Print debug line
      debug_blockchain_forward(node_out_file, lp, in_msg);
      // Add transaction to the mempool
      s->mempool = array_insert(s->mempool, in_msg->tx);
      break;
    default:
      printf("Blockchain: unhandeled forward message type %s\n", getEventName(in_msg->type));
      exit(-1);
  }
  in_msg->rng_count = lp->rng->count - rng_start_count;
  in_msg->computation_time = (double) (tw_clock_read() - start_time) / g_tw_clock_rate;
}

void blockchain_reverse(struct blockchain *s, tw_bf *bf, struct message *in_msg, tw_lp *lp) {
  // Print debug line
  debug_blockchain_reverse(node_out_file, lp, in_msg);

  // Undo event related actions that modified the blockchain state
  switch (in_msg->type) {
    case TICK_TOCK_NEXT_BLOCK:
      // Take the latest added block
      struct block* latest_block = array_get(s->blocks, array_len(s->blocks)-1);

      // Take transactions from the blocks, add them to the mempool
      while ( array_len(latest_block->transactions) ) {
        struct blockchain_tx* tx = array_get(latest_block->transactions, array_len(latest_block->transactions)-1);
        array_delete_element_nofree(latest_block->transactions, array_len(latest_block->transactions)-1);
        s->mempool = array_insert(s->mempool, tx);
      }

      // Delete the latest block from the chain
      array_delete_element(s->blocks, array_len(s->blocks)-1);
      break;
    case BC_TX_BROADCAST:
      int broadcast_tx_found_in_mempool = 0;
      for (int i=0; i<array_len(s->mempool); i++) {
        struct blockchain_tx* tx2 = array_get(s->mempool, i);
        // Here we have to check equality of the pointers directly, since two events for the same on chain tx can be generated
        if(in_msg->tx == tx2){
          broadcast_tx_found_in_mempool = 1;
          array_delete_element(s->mempool, i);
          // The above instruction also frees the transaction, so the next free is not needed
          // free(in_msg->tx);
          break;
        }
      }
      if (broadcast_tx_found_in_mempool==0){
        printf("ERROR: blockchain tx cannot be found in the mempool during the BC_TX_BROADCAST reverse handler\n");
        exit(-1);
      }
      break;
  }

  // Undo all rng calls
  long rng_count = in_msg->rng_count;
  while(rng_count--){
    tw_rand_reverse_unif(lp->rng);
  }
}

void blockchain_commit(struct blockchain *s, tw_bf *bf, struct message *in_msg, tw_lp *lp) {
  debug_blockchain_commit(node_out_file, lp, in_msg);
}

void blockchain_final(struct blockchain *s, tw_lp *lp) {
  // Check the output directory
  DIR* results_dir = opendir(output_dir_name);
  if(!results_dir){
    printf("ERROR: blockchain.c cannot find the output directory (%s).\n", output_dir_name);
    exit(EXIT_FAILURE);
  }

  // Build the filename
  char formatted_filename[50];
  sprintf(formatted_filename, "/blockchain_output_%ld.csv", g_tw_mynode);

  char output_filename[PATH_MAX];
  strcpy(output_filename, output_dir_name);
  strcat(output_filename, formatted_filename);

  // Try open the blockchain output file
  FILE* csv_blockchain_output = fopen(output_filename, "w");
  if(csv_blockchain_output  == NULL) {
    printf("ERROR: blockchain.c cannot open blockchain_output.csv\n");
    exit(EXIT_FAILURE);
  }

  // Write the header to the csv
  fprintf(csv_blockchain_output, "confirmed, block.height, block.time, tx.type, tx.sender, tx.receiver,tx.amount, tx.start_time, tx.originator\n");

  // Print the blockchain transactions
  for(int i=0; i<array_len(s->blocks); i++) {
    struct block* block = array_get(s->blocks, i);
    for (int j=0; j<array_len(block->transactions); j++){
      struct blockchain_tx* tx = array_get(block->transactions, j);
      // Write the transaction to the csv
      fprintf(csv_blockchain_output, "%d, %3d, %10.2f, %s, %6ld, %6ld, %6ld, %10.2f, %6ld\n",
        1, i, block->confirmation_time, getTxType(tx->type), tx->sender, tx->receiver, tx->amount, tx->start_time, tx->originator);
    }
  }

  // Print the mempool
  for (int j=0; j<array_len(s->mempool); j++){
    struct blockchain_tx* tx = array_get(s->mempool, j);
    // Write the transaction to the csv
    fprintf(csv_blockchain_output, "%d,    ,           , %s, %6ld, %6ld, %6ld, %10.2f, %6ld\n",
      0, getTxType(tx->type), tx->sender, tx->receiver, tx->amount, tx->start_time, tx->originator);
  }

  // Close the file and the results dir
  fclose(csv_blockchain_output);
  closedir(results_dir);

  // Deallocate the mempool
  array_free(s->mempool);

  // Deallocate blocks
  for (int i=0; i<array_len(s->blocks); i++) {
    struct block* block = array_get(s->blocks, i);
    array_free(block->transactions);
  }
  array_free(s->blocks);
}

void serialize_blockchain_tx(struct blockchain_tx* tx, char* serialized){
  if (!tx || !serialized) {
      return; // Invalid input or insufficient buffer size
  }
  char* current_pos = serialized + sizeof(size_t); // leave space for the size at the beginning

  // Serialize the payment
  // Serialize payment fields
  memcpy(current_pos, &tx->type, sizeof(tx->type));
  current_pos += sizeof(tx->type);

  memcpy(current_pos, &tx->sender, sizeof(tx->sender));
  current_pos += sizeof(tx->sender);

  memcpy(current_pos, &tx->receiver, sizeof(tx->receiver));
  current_pos += sizeof(tx->receiver);

  memcpy(current_pos, &tx->amount, sizeof(tx->amount));
  current_pos += sizeof(tx->amount);

  memcpy(current_pos, &tx->start_time, sizeof(tx->start_time));
  current_pos += sizeof(tx->start_time);

  memcpy(current_pos, &tx->originator, sizeof(tx->originator));
  current_pos += sizeof(tx->originator);

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

struct blockchain_tx* deserialize_blockchain_tx(const char* serialized){
  struct blockchain_tx* tx;
  size_t tx_size = 0;

  const char *current_pos = serialized;

  // Read the size of the serialized data
  memcpy(&tx_size, current_pos, sizeof(tx_size));
  current_pos += sizeof(tx_size);

  // Allocate memory for the tx structure
  tx = malloc(sizeof(struct blockchain_tx));

  // Read tx fields
  memcpy(&tx->type, current_pos, sizeof(tx->type));
  current_pos += sizeof(tx->type);

  memcpy(&tx->sender, current_pos, sizeof(tx->sender));
  current_pos += sizeof(tx->sender);

  memcpy(&tx->receiver, current_pos, sizeof(tx->receiver));
  current_pos += sizeof(tx->receiver);

  memcpy(&tx->amount, current_pos, sizeof(tx->amount));
  current_pos += sizeof(tx->amount);

  memcpy(&tx->start_time, current_pos, sizeof(tx->start_time));
  current_pos += sizeof(tx->start_time);

  memcpy(&tx->originator, current_pos, sizeof(tx->originator));
  current_pos += sizeof(tx->originator);

  // Verify that the remaining evt_size is 0
  if (current_pos - serialized - tx_size != 0) {
    // Handle deserialization error (unexpected data size)
    printf("ERROR: blockchain tx unexpected data size during deserialization\n");
    exit(-1);
  }

  // Return the deserialized payment
  return tx;
}
