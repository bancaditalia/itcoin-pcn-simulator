#include <ctype.h>
#include <limits.h>

#include "load.h"
#include "global.h"

#include "../utils/logging.h"
#include "../utils/array.h"
#include "../utils/utils.h"

typedef enum {
  POS, ECOM, P2P
} tx_generator_scenario;

typedef struct tx_generator_event_info {
  long id;
  enum payment_type type;
  long sender;
  long receiver;
  uint64_t amount;
} tx_generator_event_info;

const tx_generator_scenario payment_scenario_values[3] = {
  POS, ECOM, P2P
};
const int payment_scenario_pdf[3] = {
  800, 170, 3
};

const int amount_range_values[7] = {
  0, 1, 2, 3, 4, 5, 6
};
const int amount_range_given_pos_pdf[7] = {
  210, 170, 210, 130, 130, 100, 50
};
const int amount_range_given_p2p_pdf[7] = {
  140, 110, 220, 160, 140, 110, 120
};
const int amount_range_given_ecom_pdf[7] = {
  100, 110, 200, 150, 170, 160, 110
};
const int amount_ranges[7][2] = {
  {1, 500},
  {501, 1000},
  {1001, 2000},
  {2001, 3000},
  {3001, 5000},
  {5001, 10000},
  {10001, 100000}
};

int num_end_users = 0;

struct tx_generator_state g_pe_tx_generator_state;

/*
  nodes_indexed
  [type 0(END_USER)/1(MERCHANT)/2(INTERMEDIARY)/3(CB)]
  [size 0(SMALL)/1(MEDIUM)/(BIG)]
  [country ] depending on the hash table of countries arrays of pointers to nodes
*/
struct array *g_pe_nodes_indexes[4][3][NUM_COUNTRIES];

const void* get_random_value_from_discrete_distribution(tw_rng_stream* rng, const int* pdf, const void* values, int size, int sizeof_type) {
  int total_probability = 0;
  for (int i=0; i<size; ++i) {
    total_probability += pdf[i];
  }

  // rnd is a random number between 0 and the total probability sum
  long rnd = tw_rand_integer(rng, 1, total_probability);

  // Determine which integer to select based on cumulative probabilities
  int cum_probability = 0;
  for (int i=0; i<size; ++i) {
    cum_probability += pdf[i];
    if (rnd < cum_probability) {
      return values + i*sizeof_type; // Return the selected integer
    }
  }
  return values + (size-1)*sizeof_type;
}

double get_tps_for_lp_at_current_time(const tw_lp *lp) {
  const tw_stime current_time_ms = tw_now(lp);

  unsigned int payment_rate_idx = floor((current_time_ms*TPS_CFG_MAX_ROWS)/g_tw_ts_end);

  if (payment_rate_idx >= TPS_CFG_MAX_ROWS) {
    fprintf(
      stderr,
      "ERROR: computed a payment_rate_idx (%d) >= TPS_CFG_MAX_ROWS (%d). This is should never happen, and is probably a bug",
      payment_rate_idx,
      TPS_CFG_MAX_ROWS
    );
    exit(EXIT_FAILURE);
  }

  return g_pe_tx_generator_state.target_payment_rate[payment_rate_idx];
} // get_tps_for_lp_at_current_time()

double get_next_time_slot_when_tps_changes(const tw_lp *lp, tw_stime *delta_time_ms) {
  const tw_stime current_time_ms = tw_now(lp);
  tw_stime step = floor(g_tw_ts_end / TPS_CFG_MAX_ROWS);
  tw_stime delta_to_next_window_ms = step - (current_time_ms - floor(current_time_ms / step) * step);

  unsigned int starting_idx = floor((current_time_ms * TPS_CFG_MAX_ROWS) / g_tw_ts_end);
  double last_tps = g_pe_tx_generator_state.target_payment_rate[starting_idx];
  unsigned int current_idx = starting_idx + 1;
  while (current_idx < TPS_CFG_MAX_ROWS - 1 &&
      last_tps == g_pe_tx_generator_state.target_payment_rate[current_idx]){
    last_tps = g_pe_tx_generator_state.target_payment_rate[current_idx];
    current_idx++;
  }
  *delta_time_ms = delta_to_next_window_ms + (current_idx - (starting_idx - 1)) * step;
  return g_pe_tx_generator_state.target_payment_rate[current_idx];
} // get_next_time_slot_when_tps_changes()

/**
 * rstrip - Removes trailing whitespace from @input_string.
 * @input_string: The string to be stripped.
 *
 * Note that the first trailing whitespace is replaced with a %NUL-terminator
 * in the given string @input_string.
 *
 * modified from the strim() function in:
 * https://github.com/torvalds/linux/blob/611da07b89fdd53f140d7b33013f255bf0ed8f34/lib/string_helpers.c#L874-L897
 */
char* rstrip(char* input_string)
{
  size_t size;
  char *end;

  size = strlen(input_string);
  if (!size)
    return input_string;

  end = input_string + size - 1;
  while (end >= input_string && isspace(*end))
    end--;
  *(end + 1) = '\0';

  return input_string;
}


void read_tps_cfg_file(const char* tps_cfg_file, double(*payment_rate_array)[TPS_CFG_MAX_ROWS]) {
  // modified from https://pubs.opengroup.org/onlinepubs/9699919799/functions/getline.html#tag_16_192_06
  FILE* fp;
  char* line = NULL;
  size_t line_number = 0;
  size_t len = 0;
  ssize_t read;
  size_t count_valid_lines = 0;

  if (is_regular_file(tps_cfg_file) == false) {
    fprintf(stderr, "ERROR: %s is not a file\n", tps_cfg_file);
    exit(EXIT_FAILURE);
  }

  fp = fopen(tps_cfg_file, "r");
  if (fp == NULL) {
    fprintf(stderr, "ERROR: error opening %s\n", tps_cfg_file);
    exit(EXIT_FAILURE);
  }

  while ((read = getline(&line, &len, fp)) != -1) {
    line = rstrip(line);
    line_number += 1;

    if (line[0] == '\0') {
      continue;
    }

    if (line[0] == '#') {
      // ignore comments
      g_dbg_trace && fprintf(stderr, "DEBUG: line #%ld is a comment, ignoring\n", line_number);
      continue;
    }

    char* endptr;
    unsigned int tx_per_second_from_file = strtoimax(line, &endptr, 10);
    if (line == endptr) {
      fprintf(
        stderr,
        "ERROR: could not parse line #%ld of %s: \"%s\"\n",
        line_number,
        tps_cfg_file,
        line
      );
      exit(EXIT_FAILURE);
    }

    count_valid_lines += 1;
    g_dbg_trace && fprintf(
      stderr,
      "DEBUG: parsed %ld-th significant value from line #%ld: %d\n",
      count_valid_lines,
      line_number,
      tx_per_second_from_file
    );

    if (count_valid_lines > TPS_CFG_MAX_ROWS) {
      fprintf(
        stderr,
        "WARNING: there are too many values in %s. We'll keep only the first %d and ignore the rest\n",
        tps_cfg_file,
        TPS_CFG_MAX_ROWS
      );
      count_valid_lines = TPS_CFG_MAX_ROWS;
      break;
    }

    /* BEWARE of the casts here, or you'll lose precision */
    double rate = tx_per_second_from_file / (double) num_end_users;
    (*payment_rate_array)[count_valid_lines - 1] = rate;
    g_dbg_trace && fprintf(
      stderr,
      "INFO: rate %f stored at position %ld (0-based). Line #%ld\n",
      rate,
      count_valid_lines - 1,
      line_number
    );
  }

  if (count_valid_lines == 0) {
    fprintf(
      stderr,
      "ERROR: no valid transaction rates were found in file %s. Exiting\n",
      tps_cfg_file
    );
    exit(EXIT_FAILURE);
  }

  if (count_valid_lines < TPS_CFG_MAX_ROWS) {
    fprintf(
      stderr,
      "WARNING: there are too few values in %s. Expected: %d, found %ld. We'll keep the last value for %ld times\n",
      tps_cfg_file,
      TPS_CFG_MAX_ROWS,
      count_valid_lines,
      TPS_CFG_MAX_ROWS - count_valid_lines
    );
    double last_load = (*payment_rate_array)[count_valid_lines - 1];
    for (unsigned int i = count_valid_lines; i < TPS_CFG_MAX_ROWS; i++) {
      (*payment_rate_array)[i] = last_load;
    }
  }

  fclose(fp);
  free(line);
}

void dump_payment_rates(const double(*payment_rate_array)[TPS_CFG_MAX_ROWS]) {
  g_dbg_trace && printf("CONFIGURED PAYMENT RATES FROM THIS LP:\n");
  for (unsigned int i = 0; i < TPS_CFG_MAX_ROWS; i++) {
    /*
     * TODO: also print the time interval here, e.g.:
     *     #0      [00:00-00:15] -> 21 tx/s
     *     #1      [00:15-00:30] -> 22 tx/s
     *     ...
     *     #360    [23:45-00:00] -> 19 tx/s
     */
    g_dbg_trace && printf("#%-5d -> %7.3f tx/s\n", i, (*payment_rate_array)[i]);
  }
}

void init_node_indexes_per_pe() {
  /* Pre-initialize arrays in nodes_indexes */
  for(int itype=0; itype<4; itype++){
    for(int isize=0; isize<3; isize++){
      for(int icountry=0; icountry<NUM_COUNTRIES; icountry++){
        g_pe_nodes_indexes[itype][isize][icountry] = array_initialize(100);
      }
    }
  }

  /* Initialize nodes_indexes */
  for(int i=0; i<array_len(network->nodes); i++)
  {
    struct node* node = array_get(network->nodes, i);

    g_pe_nodes_indexes[node->type][node->size][node->country] = array_insert(g_pe_nodes_indexes[node->type][node->size][node->country], node);

    if (node->type==END_USER){
      num_end_users++;
    }
  }
}

void init_tx_generator_state_per_pe() {
  if (num_end_users == 0) {
    printf("WARNING (init_tx_generator_state_per_pe): no transaction generator on this PE\n");
  }

  // init state data
  g_pe_tx_generator_state.rollback_count = 0;

  // Set the target payment rate
  if (strcmp(tps_cfg_file, "") == 0) {
    // no tps_cfg_file given, let's read form "--tps"
    printf("INFO: no --tps-cfg parameter was passed. The tx generator will generate a constant load read from --tps (or its default value)\n");
    for (unsigned int i = 0; i < TPS_CFG_MAX_ROWS; i++) {
      g_pe_tx_generator_state.target_payment_rate[i] = tx_per_second / (double) num_end_users;
    }
  } else {
    // a tps_cfg_file was given, let's use that one and ignore "--tps"
    read_tps_cfg_file(tps_cfg_file, &g_pe_tx_generator_state.target_payment_rate);
  }
  dump_payment_rates(&g_pe_tx_generator_state.target_payment_rate);
}

void finalize_node_indexes_per_pe() {
  printf("Running finalize_node_indexes_per_pe\n");
  for (int itype = 0; itype < 4; itype++) {
    for (int isize = 0; isize < 3; isize++) {
      for (int icountry = 0; icountry < NUM_COUNTRIES; icountry++) {
        array_free(g_pe_nodes_indexes[itype][isize][icountry]);
      }
    }
  }
}

void finalize_node_pending_payments() {
  printf("Running finalize_node_pending_payments\n");
  for (uint32_t i = 0; i < array_len(network->nodes); i++) {
    struct node *node = array_get(network->nodes, i);
    if(node->rw_awaiting_payment != NULL){
      free_payment(node->rw_awaiting_payment);
      node->rw_awaiting_payment = NULL;
      node->rw_withdrawal_id = 0;
    }
    array_free(node->submarine_swaps);
  }
}

long tx_generator_get_amount(tw_rng_stream* rng, const tx_generator_scenario payment_scenario){
  // Choose the amount range given the payment scenario
  int amount_range_i = -1;
  if (payment_scenario == POS){
    const int* amount_range_i_p = get_random_value_from_discrete_distribution(rng, amount_range_given_pos_pdf, amount_range_values, 7, sizeof(int));
    amount_range_i = *amount_range_i_p;
  }
  else if (payment_scenario == ECOM){
    const int* amount_range_i_p = get_random_value_from_discrete_distribution(rng, amount_range_given_ecom_pdf, amount_range_values, 7, sizeof(int));
    amount_range_i = *amount_range_i_p;
  }
  else if (payment_scenario == P2P){
    const int* amount_range_i_p = get_random_value_from_discrete_distribution(rng, amount_range_given_p2p_pdf, amount_range_values, 7, sizeof(int));
    amount_range_i = *amount_range_i_p;
  }
  else {
    printf("tx_generator has an unknown payment scenario, it should not reach this point\n");
    exit(-1);
  }
  // Choose the payment amount
  return tw_rand_integer(rng, amount_ranges[amount_range_i][0], amount_ranges[amount_range_i][1]);
}

struct node* tx_generator_get_receiver(tw_rng_stream* rng, const struct node* sender, const tx_generator_scenario payment_scenario, double cross_border_probability)
{
  // Decide if the payment will be cross-border
  long is_cross_border = tw_rand_binomial(rng, 1, cross_border_probability);

  enum node_country receiver_country = sender->country;
  struct array* receiver_persons = g_pe_nodes_indexes[END_USER][SMALL][receiver_country];
  struct array* receiver_merchants = g_pe_nodes_indexes[MERCHANT][SMALL][receiver_country];

  // Pick a different country as long as one of the conditions is true ...
  long start_country_idx = tw_rand_integer(rng, 0, NUM_COUNTRIES-1);
  for (int i=0; i<NUM_COUNTRIES; i++){
    if (
      is_cross_border && receiver_country==sender->country
      || (payment_scenario == POS || payment_scenario == ECOM) && array_len(receiver_merchants) < 1 // i.e. the receiver
      || payment_scenario == P2P && array_len(receiver_persons) < 2 // i.e. the sender and the receiver
    ){
      // Select another country
      receiver_country = (start_country_idx+i) % NUM_COUNTRIES;
      receiver_persons = g_pe_nodes_indexes[END_USER][SMALL][receiver_country];
      receiver_merchants = g_pe_nodes_indexes[MERCHANT][SMALL][receiver_country];
    }
    else break;
  }

  // Select the receiver, depending on the scenario
  struct node* receiver = NULL;
  do {
    if (payment_scenario == POS || payment_scenario == ECOM){
      long receiver_idx = tw_rand_integer(rng, 0, array_len(receiver_merchants)-1);
      receiver = array_get(receiver_merchants, receiver_idx);
    }
    else if (payment_scenario == P2P){
      long receiver_idx = tw_rand_integer(rng, 0, array_len(receiver_persons)-1);
      receiver = array_get(receiver_persons, receiver_idx);
    }
    else {
      printf("tx_generator has an unknown payment scenario, it should not reach this point\n");
      exit(-1);
    }
  } while(sender->id==receiver->id);

  return receiver;
}

void schedule_next_generate_payment(tw_lp *lp,
                                    unsigned int routing_latency,
                                    unsigned int pmt_delay) {
  // Create a new GENERATE_PAYMENT message to my self in 1/TPS second
  // An exponential distribution is used to generate the next offset in 0-(1/TPS) seconds
  double tps_now = get_tps_for_lp_at_current_time(lp);
  double next_payment_event_ms = round(tw_rand_exponential(lp->rng, (1000 / tps_now)));
  {
    tw_stime delta_time_ms = 0;
    double tps_next = get_next_time_slot_when_tps_changes(lp, &delta_time_ms);
    if (delta_time_ms < next_payment_event_ms && tps_now != tps_next) {
      next_payment_event_ms = delta_time_ms;
      next_payment_event_ms += round(tw_rand_exponential(lp->rng, (1000 / tps_next)));
    }
  }

  tw_stime event_offset_ms = fmax(routing_latency + pmt_delay + 1, next_payment_event_ms);

  tw_event *next_generate_event = tw_event_new(lp->gid, event_offset_ms, lp);
  message *next_generate_msg = tw_event_data(next_generate_event);
  next_generate_msg->type = GENERATE_PAYMENT;
  memset(&next_generate_msg->data[0], 0, sizeof(next_generate_msg->data));
  tw_event_send(next_generate_event);
}

// Generate random payment
void generate_next_random_payment(node *sender, tw_bf *bf, message *in_msg, tw_lp *lp) {
  if (in_msg->type != GENERATE_PAYMENT){
    printf("Tx generator of physical entity %ld received event with type != GENERATE_PAYMENT\n", lp->pe->id);
    exit(-1);
  }

  // Initial count of the random generator
  unsigned long rng_initial_count = lp->rng->count;

  // If I am already awaiting a payment, delay this generate random
  if(rev_waterfall_enabled && sender->rw_awaiting_payment != NULL){
    memset(&in_msg->data[0], 0, sizeof(in_msg->data));
    tw_stime event_offset = tw_rand_integer(lp->rng, 1, RETRY_GENERATE_RANDOM_MAX_OFFSET);
    tw_event *next_generate_event = tw_event_new(lp->gid, event_offset, lp);
    message *next_generate_msg = tw_event_data(next_generate_event);
    next_generate_msg->type = GENERATE_PAYMENT;
    tw_event_send(next_generate_event);
    in_msg->rng_count = lp->rng->count - rng_initial_count;
    return;
  }

  // Select the sender, that is always a person among the managed ones
  uint64_t sender_wallet_cap_u = get_node_wallet_cap(network, sender);
  uint64_t sender_available_balance_u = get_node_available_balance(sender);

  // NOTE: Here, we use an unsigned int 64 (8bytes) in operations with sign. To this end, we cast it to long long (8 bytes)
  if (sender_wallet_cap_u >= LLONG_MAX) {
    fprintf(
            stderr,
            "WARNING: sender_wallet_cap (%lu) cannot be safely casted to a signed 8-byte data type.\n",
            sender_wallet_cap_u
    );
  }
  if (sender_available_balance_u >= LLONG_MAX) {
    fprintf(
            stderr,
            "WARNING: unsigned sender_available_balance (%lu) cannot be safely casted to a signed 8-byte data type.\n",
            sender_available_balance_u
    );
  }
  long long sender_wallet_cap_ll = (long long) sender_wallet_cap_u;
  long long sender_available_balance_ll = (long long) sender_available_balance_u;

  // Choose the payment scenario
  const tx_generator_scenario payment_scenario = *( (tx_generator_scenario*) get_random_value_from_discrete_distribution(lp->rng, payment_scenario_pdf, payment_scenario_values, 3, sizeof(tx_generator_scenario)) );
  // For consistency between operands, store amounts in an 8-bytes long
  long long amount = (long long) tx_generator_get_amount(lp->rng, payment_scenario);
  if (amount > sender_wallet_cap_ll){
    printf("WARN: Tx generator generated a payment with amount %lld, that is higher than sender %ld wallet cap %lld.\n",
      amount,
      sender->id,
      sender_wallet_cap_ll
    );
    amount = sender_wallet_cap_ll;
  }
  // Select the receiver
  struct node* receiver = tx_generator_get_receiver(lp->rng, sender, payment_scenario, 0.05);
  // Create the payment
  struct payment* pmt_to_forward = NULL;
  // Check that the sender has enough balance to send the payment
  if (rev_waterfall_enabled && sender_available_balance_ll < amount){
    // Create a withdrawal
    // Here decide the withdrawal amount,
    // Taking into account: the base wallet amount (250 constant) and the difference between the payment amount and the current balance. In formula: W = max (Wbase − B, Pa − B)
    uint64_t amount_w;
    // cap amount_w to 25000, i.e., amount = min(payment amount, 250)
    if (25000LL - sender_available_balance_ll > amount - sender_available_balance_ll){
      // NOTE: here we are converting a signed 8byte to an unsigned 8bytes. No information loss.
      amount_w = (uint64_t) (25000LL - sender_available_balance_ll);
    } else{
      // NOTE: here we are converting a signed 8byte to an unsigned 8bytes. No information loss.
      amount_w = (uint64_t) (amount - sender_available_balance_ll);
    }
    pmt_to_forward = new_payment(sender->custodian_id, sender->id, amount_w, tw_now(lp), WITHDRAWAL);
    // Create the postponed payment
    struct payment* postponed_payment = new_payment(sender->id, receiver->id, amount, tw_now(lp), TX);
    postponed_payment->last_hop_id = receiver->lsp_id; // The last hop of a payment should be from the LSP to the receiver
    // Append the original payment to the pending payments list of the sender
    sender->rw_awaiting_payment = postponed_payment;
    sender->rw_withdrawal_id = pmt_to_forward->id;
  }
  else {
    pmt_to_forward = new_payment(sender->id, receiver->id, amount, tw_now(lp), TX);
    pmt_to_forward->last_hop_id=receiver->lsp_id; // The last hop of a payment should be from the LSP to the receiver
  }
  // We log here the msg receive because it's the first place where we know the payment to forward id
  debug_node_generate_forward(node_out_file, lp, in_msg, pmt_to_forward->id);
  // Just an error check
  if (! (pmt_to_forward->type == WITHDRAWAL || pmt_to_forward->type == TX) ) {
    printf("tx_generator has has generated something different from a WITHDRAWAL or a TX, this should not happen for now\n");
    exit(-1);
  }

  // Select the router and forward the FIND_PATH event
  unsigned int pmt_delay = pmt_to_forward->type==WITHDRAWAL ? tw_rand_gamma(lp->rng, DELAY_GAMMA_DISTR_ALPHA, DELAY_GAMMA_DISTR_BETA) : 10;
  tw_event *next_e = tw_event_new(pmt_to_forward->sender, pmt_delay, lp);
  message *next_msg = tw_event_data(next_e);
  next_msg->type = FINDPATH;
  serialize_payment(pmt_to_forward, next_msg->data);
  tw_event_send(next_e);

  // Inform the simulator about the payment that we have generated, so that it can be rolled back
  tx_generator_event_info event_info = {
    .id = pmt_to_forward->id,
    .type = pmt_to_forward->type,
    .sender = pmt_to_forward->sender,
    .receiver = pmt_to_forward->receiver,
    .amount = pmt_to_forward->amount
  };
  memcpy(in_msg->data, &event_info, sizeof(event_info));

  schedule_next_generate_payment(lp, ROUTING_LATENCY, pmt_delay);

  in_msg->rng_count = lp->rng->count - rng_initial_count;
  // Here we can deallocate the pmt_to_forward
  // NB: if the pmt_to_forward was a WITHDRAWAL, then the awaiting payment will be deallocated in the rollback
  free_payment(pmt_to_forward);
}

// Rollback withdrawals if created in generate random payment
void rollback_withdrawal_if_any(tw_bf *bf, message *in_msg, tw_lp *lp) {
  // Increment the rollback count
  g_pe_tx_generator_state.rollback_count++;
  // If the event was the initial event, or the forward handler didn't generate any payment we do not have to rollback anything
  {
    int sum = 0;
    for (int i = 0; i < 10; ++i) {
      sum |= in_msg->data[i];
    }
    if (sum==0) return;
  }
  // Deserialize the generated payment
  struct tx_generator_event_info payment;
  memcpy(&payment, in_msg->data, sizeof(payment));
  // Log the rollback receive event
  debug_node_generate_reverse(node_out_file, lp, in_msg, payment.id);
  // If the payment is a withdrawal, we remove the awaiting payment
  if (payment.type == WITHDRAWAL){
    struct node* receiver = array_get(network->nodes, payment.receiver);
    if(receiver->rw_awaiting_payment != NULL && receiver->rw_withdrawal_id == payment.id){
      free_payment(receiver->rw_awaiting_payment);
      receiver->rw_awaiting_payment = NULL;
      receiver->rw_withdrawal_id = 0;
    }
  }
}
