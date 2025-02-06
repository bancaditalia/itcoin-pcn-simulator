#include "logging.h"

#include "../features/payments.h"
#include "../features/submarine_swaps.h"
#include "../model/message.h"

// Enable tracing
int g_dbg_trace=0;

void debug_lp(char lp_name[5], tw_lp* lp, char* out){
  snprintf(out, DEBUG_BUF_SIZE, "%s #%7lu @%2.3f", lp_name, lp->gid, tw_now(lp));
}

void debug_msg(struct message* msg, char* out){
  snprintf(out, DEBUG_BUF_SIZE, "%s", getEventName(msg->type));
}

void debug_payment(struct payment* payment, char* out){
  snprintf(out, DEBUG_BUF_SIZE, "pmt.id %12ld", payment->id);
}

void debug_submarine_swap(struct submarine_swap* swap, char* out){
  snprintf(out, DEBUG_BUF_SIZE, "swap.ssndr %lu swap.srcvr %lu swap.amt %ld swap.tp %12ld",
    swap->submarine_sender, swap->submarine_receiver, swap->amount, swap->trigger_payment_id);
}

void debug_blockchain_tx(struct blockchain_tx* tx, char* out){
  snprintf(out, DEBUG_BUF_SIZE, "tx.type: %s tx.orig %lu tx.sndr %lu tx.rcvr %lu tx.amt %lu tx.st %2.3f",
    getTxType(tx->type), tx->originator, tx->sender, tx->receiver, tx->amount, tx->start_time);
}

void debug_node_forward(FILE* node_out_file, tw_lp* lp, struct message* msg){
  if (g_dbg_trace){
    char lpstr[DEBUG_BUF_SIZE];
    char msgstr[DEBUG_BUF_SIZE];
    char objectstr[DEBUG_BUF_SIZE];
    debug_lp("NODE", lp, lpstr);
    debug_msg(msg, msgstr);
    switch (msg->type) {
      case FINDPATH:
      case SENDPAYMENT:
      case FORWARDPAYMENT:
      case RECEIVEPAYMENT:
      case FORWARDSUCCESS:
      case RECEIVESUCCESS:
      case FORWARDFAIL:
      case RECEIVEFAIL:
      case NOTIFYPAYMENT:
        debug_payment(msg->payment, objectstr);
        fprintf(node_out_file, "FWDE: %s rcv %s %s\n", lpstr, msgstr, objectstr);
        break;
      case SWAP_REQUEST:
        debug_submarine_swap(msg->swap, objectstr);
        fprintf(node_out_file, "FWDE: %s rcv %s %s\n", lpstr, msgstr, objectstr);
        break;
      case BC_TX_CONFIRMED:
        debug_blockchain_tx(msg->tx, objectstr);
        fprintf(node_out_file, "FWDE: %s rcv %s %s\n", lpstr, msgstr, objectstr);
        break;
    };
    fflush(node_out_file);
  }
}

void debug_node_commit(FILE* node_out_file, tw_lp* lp, struct message* msg){
  if (g_dbg_trace){
    char lpstr[DEBUG_BUF_SIZE];
    char msgstr[DEBUG_BUF_SIZE];
    char objectstr[DEBUG_BUF_SIZE];
    debug_lp("NODE", lp, lpstr);
    debug_msg(msg, msgstr);
    switch (msg->type) {
      case FINDPATH:
      case SENDPAYMENT:
      case FORWARDPAYMENT:
      case RECEIVEPAYMENT:
      case FORWARDSUCCESS:
      case RECEIVESUCCESS:
      case FORWARDFAIL:
      case RECEIVEFAIL:
      case NOTIFYPAYMENT:
        debug_payment(msg->payment, objectstr);
        fprintf(node_out_file, "COMM: %s was @%2.3f rcv %s %s\n", lpstr, msg->fwd_handler_time, msgstr, objectstr);
        break;
      case SWAP_REQUEST:
        debug_submarine_swap(msg->swap, objectstr);
        fprintf(node_out_file, "COMM: %s was @%2.3f rcv %s %s\n", lpstr, msg->fwd_handler_time, msgstr, objectstr);
        break;
      case BC_TX_CONFIRMED:
        debug_blockchain_tx(msg->tx, objectstr);
        fprintf(node_out_file, "COMM: %s was @%2.3f rcv %s %s\n", lpstr, msg->fwd_handler_time, msgstr, objectstr);
        break;
    };
    fflush(node_out_file);
  }
}

void debug_node_reverse(FILE* node_out_file, tw_bf *bf, tw_lp* lp, struct message* msg){
  if (g_dbg_trace){
    char lpstr[DEBUG_BUF_SIZE];
    char msgstr[DEBUG_BUF_SIZE];
    char objectstr[DEBUG_BUF_SIZE];
    debug_lp("NODE", lp, lpstr);
    debug_msg(msg, msgstr);
    switch (msg->type) {
      case FINDPATH:
      case SENDPAYMENT:
      case FORWARDPAYMENT:
      case RECEIVEPAYMENT:
      case FORWARDSUCCESS:
      case RECEIVESUCCESS:
      case FORWARDFAIL:
      case RECEIVEFAIL:
      case NOTIFYPAYMENT:
        debug_payment(msg->payment, objectstr);
        fprintf(node_out_file, "REVE: %s rev %s %s bf[0] %d\n", lpstr, msgstr, objectstr, bf->c0);
        break;
      case SWAP_REQUEST:
        debug_submarine_swap(msg->swap, objectstr);
        fprintf(node_out_file, "REVE: %s rev %s %s\n", lpstr, msgstr, objectstr);
        break;
      case BC_TX_CONFIRMED:
        debug_blockchain_tx(msg->tx, objectstr);
        fprintf(node_out_file, "REVE: %s rev %s %s\n", lpstr, msgstr, objectstr);
        break;
    };
    fflush(node_out_file);
  }
}

void debug_node_generate_forward(FILE* node_out_file, tw_lp* lp, struct message* msg, long payment_id){
  if (g_dbg_trace){
    char lpstr[DEBUG_BUF_SIZE];
    char msgstr[DEBUG_BUF_SIZE];
    debug_lp("NODE", lp, lpstr);
    debug_msg(msg, msgstr);
    fprintf(node_out_file, "FWDE: %s rcv %s pmt.id %12ld\n", lpstr, msgstr, payment_id);
    fflush(node_out_file);
  }
}

void debug_node_generate_reverse(FILE* node_out_file, tw_lp* lp, struct message* msg, long payment_id){
  if (g_dbg_trace){
    char lpstr[DEBUG_BUF_SIZE];
    char msgstr[DEBUG_BUF_SIZE];
    debug_lp("NODE", lp, lpstr);
    debug_msg(msg, msgstr);
    fprintf(node_out_file, "REVE: %s rev %s pmt.id %12ld\n", lpstr, msgstr, payment_id);
    fflush(node_out_file);
  }
}

void debug_blockchain_forward(FILE* node_out_file, tw_lp* lp, struct message* msg){
  if (g_dbg_trace){
    char lpstr[DEBUG_BUF_SIZE];
    char msgstr[DEBUG_BUF_SIZE];
    char objectstr[DEBUG_BUF_SIZE];
    debug_lp("BLKC", lp, lpstr);
    debug_msg(msg, msgstr);
    switch (msg->type) {
      case TICK_TOCK_NEXT_BLOCK:
        fprintf(node_out_file, "FWDE: %s rcv %s\n", lpstr, msgstr);
        break;
      case BC_TX_BROADCAST:
        debug_blockchain_tx(msg->tx, objectstr);
        fprintf(node_out_file, "FWDE: %s rcv %s %s\n", lpstr, msgstr, objectstr);
        break;
    };
    fflush(node_out_file);
  }
}

void debug_blockchain_reverse(FILE* node_out_file, tw_lp* lp, struct message* msg){
  if (g_dbg_trace){
    char lpstr[DEBUG_BUF_SIZE];
    char msgstr[DEBUG_BUF_SIZE];
    char objectstr[DEBUG_BUF_SIZE];
    debug_lp("BLKC", lp, lpstr);
    debug_msg(msg, msgstr);
    switch (msg->type) {
      case TICK_TOCK_NEXT_BLOCK:
        fprintf(node_out_file, "REVE: %s rcv %s\n", lpstr, msgstr);
        break;
      case BC_TX_BROADCAST:
        debug_blockchain_tx(msg->tx, objectstr);
        fprintf(node_out_file, "REVE: %s rcv %s %s\n", lpstr, msgstr, objectstr);
        break;
    };
    fflush(node_out_file);
  }
}

void debug_blockchain_commit(FILE* node_out_file, tw_lp* lp, struct message* msg){
  if (g_dbg_trace){
    char lpstr[DEBUG_BUF_SIZE];
    char msgstr[DEBUG_BUF_SIZE];
    char objectstr[DEBUG_BUF_SIZE];
    debug_lp("BLKC", lp, lpstr);
    debug_msg(msg, msgstr);
    switch (msg->type) {
      case TICK_TOCK_NEXT_BLOCK:
        fprintf(node_out_file, "COMM: %s was @%2.3f rcv %s\n", lpstr, msg->fwd_handler_time, msgstr);
        break;
      case BC_TX_BROADCAST:
        debug_blockchain_tx(msg->tx, objectstr);
        fprintf(node_out_file, "COMM: %s was @%2.3f rcv %s %s\n", lpstr, msg->fwd_handler_time, msgstr, objectstr);
        break;
    };
    fflush(node_out_file);
  }
}
