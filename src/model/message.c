#include "message.h"

const char* getEventName(event_type event){
  switch(event){
    case GENERATE_PAYMENT: return     "GENERATE      ";
    case FINDPATH: return             "FINDPATH      ";
    case SENDPAYMENT: return          "SENDPAYMENT   ";
    case FORWARDPAYMENT: return       "FORWARDPAYMENT";
    case RECEIVEPAYMENT: return       "RECEIVEPAYMENT";
    case FORWARDSUCCESS: return       "FORWARDSUCCESS";
    case FORWARDFAIL: return          "FORWARDFAIL   ";
    case RECEIVESUCCESS: return       "RECEIVESUCCESS";
    case RECEIVEFAIL: return          "RECEIVEFAIL   ";
    case NOTIFYPAYMENT:   return      "NOTIFYPAYMENT ";
    case BC_TX_BROADCAST: return      "BC_TX_BRCAST  ";
    case BC_TX_CONFIRMED: return      "BC_TX_CONFIRM ";
    case TICK_TOCK_NEXT_BLOCK: return "TICK_TOCK_NEXT";
    case SWAP_REQUEST: return         "SWAP_REQUEST  ";
  }
}
