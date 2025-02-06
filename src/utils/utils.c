#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <dirent.h>

#include "array.h"
#include "utils.h"
#include "heap.h"
#include "../features/htlc.h"
#include "../features/network.h"
#include "../features/payments.h"
#include "../features/routing.h"
#include "../model/global.h"

int is_equal_result(struct node_pair_result *a, struct node_pair_result *b ){
  return a->to_node_id == b->to_node_id;
}

int is_equal_key_result(long key, struct node_pair_result *a){
  return key == a->to_node_id;
}

int is_equal_node_list_element(long key, struct node_list_element *a){
    return key == a->from_node_id;
}

int is_equal_long(long* a, long* b) {
  return *a==*b;
}

int is_key_equal(struct distance* a, struct distance* b) {
  return a->node == b->node;
}

int is_present(long element, struct array* long_array) {
  long i, *curr;

  if(long_array==NULL) return 0;

  for(i=0; i<array_len(long_array); i++) {
    curr = array_get(long_array, i);
    if(*curr==element) return 1;
  }

  return 0;
}

void free_data_structures(struct network* network, struct array* payments){
  // network
  free_network(network);
  // payments
  if(payments != NULL){
    for(int i=0; i<payments->index; i++){
      free_payment(payments->element[i]);
    }
    array_free(payments);
  }
}

bool is_regular_file(const char *path)
{
  /* modifed from: https://stackoverflow.com/questions/4553012/checking-if-a-file-is-a-directory-or-just-a-file/4553076#4553076 */
  struct stat path_stat;
  stat(path, &path_stat);
  return S_ISREG(path_stat.st_mode) != 0;
}


/* write the final values of nodes, channels, edges and payments in csv files */
void write_output(struct network* network, struct array* payments, char output_dir_name[], unsigned long pe_id) {
  FILE* csv_channel_output, *csv_edge_output, *csv_payment_output, *csv_node_output;
  long i,j, *id;
  struct channel* channel;
  struct edge* edge;
  struct payment* payment;
  struct node* node;
  struct route* route;
  struct array* hops;
  struct route_hop* hop;
  DIR* results_dir;
  char output_filename[PATH_MAX];
  char formatted_filename[50];
  struct node* sender_node = NULL;
  struct node* receiver_node = NULL;
  struct node* error_edge_from = NULL;
  struct node* error_edge_to = NULL;

  results_dir = opendir(output_dir_name);
  if(!results_dir){
    printf("cloth.c: Cannot find the output directory (%s). The output will be stored in the current directory.\n", output_dir_name);
    strcpy(output_dir_name, "./");
  }

  strcpy(output_filename, output_dir_name);
  sprintf(formatted_filename, "/channels_output_%ld.csv", pe_id);
  strcat(output_filename, formatted_filename);
  csv_channel_output = fopen(output_filename, "w");
  if(csv_channel_output  == NULL) {
    printf("ERROR cannot open channel_output.csv\n");
    exit(-1);
  }
  fprintf(csv_channel_output, "id,edge1,edge2,node1,node2,capacity,is_closed,is_private\n");
  for(i=0; i<array_len(network->channels); i++) {
    channel = array_get(network->channels, i);
    sender_node = array_get(network->nodes, channel->node1);
    if (sender_node->partition != pe_id){
      // skip channels whose sender nodes are not in the current partition
      continue;
    }

    receiver_node = array_get(network->nodes, channel->node2);
    if(sender_node->label != NULL && receiver_node->label != NULL){
       fprintf(csv_channel_output, "%ld,%ld,%ld,%s,%s,%ld,%d\n", channel->id, channel->edge1, channel->edge2, sender_node->label, receiver_node->label, channel->capacity, channel->is_closed);
    } else {
      fprintf(csv_channel_output, "%ld,%ld,%ld,%ld,%ld,%ld,%d\n", channel->id, channel->edge1, channel->edge2, channel->node1, channel->node2, channel->capacity, channel->is_closed);
    }
  }
  fclose(csv_channel_output);

  strcpy(output_filename, output_dir_name);
  sprintf(formatted_filename, "/edges_output_%ld.csv", pe_id);
  strcat(output_filename, formatted_filename);
  csv_edge_output = fopen(output_filename, "w");
  if(csv_edge_output  == NULL) {
    printf("ERROR cannot open edge_output.csv\n");
    exit(-1);
  }
  fprintf(csv_edge_output, "id,channel_id,counter_edge_id,from_node_id,to_node_id,from_node_label,to_node_label,balance,fee_base,fee_proportional,min_htlc,timelock,is_closed,tot_flows\n");
  for(i=0; i<array_len(network->edges); i++) {
    edge = array_get(network->edges, i);
    sender_node = array_get(network->nodes, edge->from_node_id);
    if (sender_node->partition != pe_id){
      // skip edges whose sender nodes are not in the current partition
      continue;
    }

    receiver_node = array_get(network->nodes, edge->to_node_id);
    if(sender_node->label != NULL && receiver_node->label != NULL){
      fprintf(csv_edge_output, "%ld,%ld,%ld,%ld,%ld,%s,%s,%ld,%ld,%ld,%ld,%d,%d,%ld\n", edge->id, edge->channel_id, edge->counter_edge_id, edge->from_node_id, edge->to_node_id, sender_node->label, receiver_node->label, edge->balance, edge->policy.fee_base, edge->policy.fee_proportional, edge->policy.min_htlc, edge->policy.timelock, edge->is_closed, edge->tot_flows);
    } else {
      fprintf(csv_edge_output, "%ld,%ld,%ld,%ld,%ld,"","",%ld,%ld,%ld,%ld,%d,%d,%ld\n", edge->id, edge->channel_id, edge->counter_edge_id, edge->from_node_id, edge->to_node_id, edge->balance, edge->policy.fee_base, edge->policy.fee_proportional, edge->policy.min_htlc, edge->policy.timelock, edge->is_closed, edge->tot_flows);
    }
  }
  fclose(csv_edge_output);

  strcpy(output_filename, output_dir_name);
  sprintf(formatted_filename, "/payments_output_%ld.csv", pe_id);
  strcat(output_filename, formatted_filename);
  csv_payment_output = fopen(output_filename, "w");
  if(csv_payment_output  == NULL) {
    printf("ERROR cannot open payment_output.csv\n");
    exit(-1);
  }
  fprintf(csv_payment_output, "id,type,sender_id,receiver_id,amount,start_time,end_time,mpp,is_success,no_balance_count,offline_node_count,timeout_exp,attempts,first_no_balance_error,route,route_ids,total_fee\n");
  for(i=0; i<array_len(payments); i++)  {
    payment = array_get(payments, i);
    if (payment->id == -1) continue;
    sender_node = array_get(network->nodes, payment->sender);
    receiver_node = array_get(network->nodes, payment->receiver);
    if(sender_node->label != NULL && receiver_node->label != NULL){
      fprintf(csv_payment_output, "%ld,%d,%s,%s,%ld,%ld,%ld,%u,%u,%d,%d,%u,%d,", payment->id, payment->type, sender_node->label, receiver_node->label, payment->amount, payment->start_time, payment->end_time, payment->is_shard, payment->is_success, payment->no_balance_count, payment->offline_node_count, payment->is_timeout, payment->attempts);
    } else {
      fprintf(csv_payment_output, "%ld,%d,%ld,%ld,%ld,%ld,%ld,%u,%u,%d,%d,%u,%d,", payment->id, payment->type, payment->sender, payment->receiver, payment->amount, payment->start_time, payment->end_time, payment->is_shard, payment->is_success, payment->no_balance_count, payment->offline_node_count, payment->is_timeout, payment->attempts);
    }
    if (!payment->is_success && payment->error.type != NOERROR && payment->error.type == NOBALANCE){
      error_edge_from = array_get(network->nodes, payment->error.hop->from_node_id);
      error_edge_to = array_get(network->nodes, payment->error.hop->to_node_id);
      fprintf(csv_payment_output,"%ld:%ld:%s->%s,",  payment->error.hop->edge_id, payment->error.time, error_edge_from->label, error_edge_to->label);
    } else {
      fprintf(csv_payment_output,",");
    }
    route = payment->route;
    if(route==NULL)
      fprintf(csv_payment_output, ",-1,");
    else {
      hops = route->route_hops;
      for(j=0; j<array_len(hops); j++) {
        hop = array_get(hops, j);
        edge = array_get(network->edges, hop->edge_id);
        sender_node = array_get(network->nodes, edge->from_node_id);
        receiver_node = array_get(network->nodes, edge->to_node_id);
        if(j==array_len(hops)-1){
          if(sender_node->label != NULL && receiver_node->label != NULL){
            fprintf(csv_payment_output,"%s->%s,", sender_node->label, receiver_node->label);
          } else {
            fprintf(csv_payment_output,",");
          }
        }
        else {
          if(sender_node->label != NULL && receiver_node->label != NULL){
            fprintf(csv_payment_output,"%s->%s-",sender_node->label, receiver_node->label);
          } else {
            fprintf(csv_payment_output,"-");
          }
        }

      }
      for(j=0; j<array_len(hops); j++) {
        hop = array_get(hops, j);
        edge = array_get(network->edges, hop->edge_id);
        sender_node = array_get(network->nodes, edge->from_node_id);
        receiver_node = array_get(network->nodes, edge->to_node_id);
        if(j==array_len(hops)-1){
          fprintf(csv_payment_output,"%ld,",hop->edge_id);
        }
        else {
          fprintf(csv_payment_output,"%ld-",hop->edge_id);
        }
      }
      fprintf(csv_payment_output, "%ld",route->total_fee);
    }
    fprintf(csv_payment_output,"\n");
  }
  fclose(csv_payment_output);

  strcpy(output_filename, output_dir_name);
  sprintf(formatted_filename, "/nodes_output_%ld.csv", pe_id);
  strcat(output_filename, formatted_filename);
  csv_node_output = fopen(output_filename, "w");
  if(csv_node_output  == NULL) {
    printf("ERROR cannot open nodes_output.csv\n");
    return;
  }
  fprintf(csv_node_output, "id,open_edges\n");
  for(i=0; i<array_len(network->nodes); i++) {
    node = array_get(network->nodes, i);
    if (node->partition != pe_id){
      // skip nodes that are not in the current partition
      continue;
    }

    fprintf(csv_node_output, "%ld,", node->id);
    if(array_len(node->open_edges)==0)
      fprintf(csv_node_output, "-1");
    else {
      for(j=0; j<array_len(node->open_edges); j++) {
        id = array_get(node->open_edges, j);
        if(j==array_len(node->open_edges)-1)
          fprintf(csv_node_output,"%ld",*id);
        else
          fprintf(csv_node_output,"%ld-",*id);
      }
    }
    fprintf(csv_node_output,"\n");
  }
  fclose(csv_node_output);
  closedir(results_dir);
}
