#ifndef _logging_h
#define _logging_h

#include "../features/payments.h"
#include "../features/submarine_swaps.h"
#include "../model/blockchain.h"
#include "../model/message.h"

#define DEBUG_BUF_SIZE 500

void debug_lp(char lp_name[5], tw_lp* lp, char* out);
void debug_msg(message* msg, char* out);
void debug_payment(struct payment* payment, char* out);
void debug_submarine_swap(struct submarine_swap* swap, char* out);
void debug_blockchain_tx(struct blockchain_tx* tx, char* out);

void debug_node_forward(FILE* node_out_file, tw_lp* lp, message* msg);
void debug_node_reverse(FILE* node_out_file, tw_bf *bf, tw_lp* lp, message* msg);
void debug_node_commit(FILE* node_out_file, tw_lp* lp, message* msg);

void debug_node_generate_forward(FILE* node_out_file, tw_lp* lp, message* msg, long payment_id);
void debug_node_generate_reverse(FILE* node_out_file, tw_lp* lp, message* msg, long payment_id);

void debug_blockchain_forward(FILE* node_out_file, tw_lp* lp, message* msg);
void debug_blockchain_reverse(FILE* node_out_file, tw_lp* lp, message* msg);
void debug_blockchain_commit(FILE* node_out_file, tw_lp* lp, message* msg);

#endif
