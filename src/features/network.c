#include <stdlib.h>
#include <string.h>
#include <linux/limits.h>

#include "network.h"
#include "routing.h"
#include "../utils/list.h"
#include "../utils/array.h"

/* Functions in this file generate a payment-channel network where to simulate the execution of payments */


struct node* new_node(long id, char* label, enum node_type node_type, enum node_size node_size, enum node_country node_country) {
  struct node* node;
  node = malloc(sizeof(struct node));
  node->id=id;
  node->label=NULL;
  if(label != NULL){
    node->label=malloc(sizeof(char) * (strlen(label)+1));
    strcpy(node->label, label);
  }
  node->type=node_type;
  node->size=node_size;
  node->country = node_country;
  node->open_edges = array_initialize(10);
  node->rw_awaiting_payment = NULL;
  node->rw_withdrawal_id = 0;
  node->submarine_swaps = array_initialize(10);
  node->results = NULL;
  node->explored = 0;
  return node;
}


struct channel* new_channel(long id, long direction1, long direction2, long node1, long node2, uint64_t capacity, unsigned int is_private) {
  struct channel* channel;
  channel = malloc(sizeof(struct channel));
  channel->id = id;
  channel->edge1 = direction1;
  channel->edge2 = direction2;
  channel->node1 = node1;
  channel->node2 = node2;
  channel->capacity = capacity;
  channel->is_closed = 0;
  channel->is_private = is_private;
  return channel;
}


struct edge* new_edge(long id, long channel_id, long counter_edge_id, long from_node_id, long to_node_id, uint64_t balance, struct policy policy){
  struct edge* edge;
  edge = malloc(sizeof(struct edge));
  edge->id = id;
  edge->channel_id = channel_id;
  edge->from_node_id = from_node_id;
  edge->to_node_id = to_node_id;
  edge->counter_edge_id = counter_edge_id;
  edge->policy = policy;
  edge->balance = balance;
  edge->is_closed = 0;
  edge->tot_flows = 0;
  return edge;
}


/* after generating a network, write it in csv files "nodes.csv" "edges.csv" "channels.csv" */
void write_network_files(struct network* network){
  FILE* nodes_output_file, *edges_output_file, *channels_output_file;
  long i;
  struct node* node;
  struct channel* channel;
  struct edge* edge;

  nodes_output_file = fopen("nodes.csv", "w");
  if(nodes_output_file==NULL) {
    fprintf(stderr, "ERROR: cannot open file <%s>\n", "nodes.csv");
    exit(-1);
  }
  fprintf(nodes_output_file, "id\n");
  channels_output_file = fopen("channels.csv", "w");
  if(channels_output_file==NULL) {
    fprintf(stderr, "ERROR: cannot open file <%s>\n", "channels.csv");
    fclose(nodes_output_file);
    exit(-1);
  }
  fprintf(channels_output_file, "id,edge1_id,edge2_id,node1_id,node2_id,capacity,is_private\n");
  edges_output_file = fopen("edges.csv", "w");
  if(edges_output_file==NULL) {
    fprintf(stderr, "ERROR: cannot open file <%s>\n", "edges.csv");
    fclose(nodes_output_file);
    fclose(channels_output_file);
    exit(-1);
  }
  fprintf(edges_output_file, "id,channel_id,counter_edge_id,from_node_id,to_node_id,balance,fee_base,fee_proportional,min_htlc,timelock\n");

  for(i=0; i<array_len(network->nodes); i++){
    node = array_get(network->nodes, i);
    fprintf(nodes_output_file, "%ld\n", node->id);
  }

  for(i=0; i<array_len(network->channels); i++){
    channel = array_get(network->channels, i);
    fprintf(channels_output_file, "%ld,%ld,%ld,%ld,%ld,%ld,%d\n", channel->id, channel->edge1, channel->edge2, channel->node1, channel->node2, channel->capacity, channel->is_private);
  }

  for(i=0; i<array_len(network->edges); i++){
    edge = array_get(network->edges, i);
    fprintf(edges_output_file, "%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%d\n", edge->id, edge->channel_id, edge->counter_edge_id, edge->from_node_id, edge->to_node_id, edge->balance, (edge->policy).fee_base, (edge->policy).fee_proportional, (edge->policy).min_htlc, (edge->policy).timelock);
  }

  fclose(nodes_output_file);
  fclose(edges_output_file);
  fclose(channels_output_file);
}


void update_probability_per_node(double *probability_per_node, int *channels_per_node, long n_nodes, long node1_id, long node2_id, long tot_channels){
  long i;
  channels_per_node[node1_id] += 1;
  channels_per_node[node2_id] += 1;
  for(i=0; i<n_nodes; i++)
    probability_per_node[i] = ((double)channels_per_node[i])/tot_channels;
}

/* generate a payment-channel network from input files */
enum node_country country_string2enum(const char country[COUNTRYLABELSIZE]){
  if (strcmp(country, "AT") == 0)      return AT;
  else if (strcmp(country, "BE") == 0) return BE;
  else if (strcmp(country, "CY") == 0) return CY;
  else if (strcmp(country, "DE") == 0) return DE;
  else if (strcmp(country, "EE") == 0) return EE;
  else if (strcmp(country, "ES") == 0) return ES;
  else if (strcmp(country, "FI") == 0) return FI;
  else if (strcmp(country, "FR") == 0) return FR;
  else if (strcmp(country, "GR") == 0) return GR;
  else if (strcmp(country, "HR") == 0) return HR;
  else if (strcmp(country, "IE") == 0) return IE;
  else if (strcmp(country, "IT") == 0) return IT;
  else if (strcmp(country, "LT") == 0) return LT;
  else if (strcmp(country, "LU") == 0) return LU;
  else if (strcmp(country, "LV") == 0) return LV;
  else if (strcmp(country, "MT") == 0) return MT;
  else if (strcmp(country, "NL") == 0) return NL;
  else if (strcmp(country, "PT") == 0) return PT;
  else if (strcmp(country, "SI") == 0) return SI;
  else if (strcmp(country, "SK") == 0) return SK;
  else if (strcmp(country, "EU") == 0) return EU;
  else
  {
    printf("ERROR: network.c unknown country\n");
    exit(-1);
  }
}

struct network* generate_network_from_files(char nodes_filename[256], char channels_filename[256], char edges_filename[256], int force_single_partition) {
  char row[2048];
  struct node* node;
  long id, direction1, direction2, node_id1, node_id2, channel_id, other_direction;
  struct policy policy;
  uint64_t capacity, balance;
  unsigned int is_private;
  struct channel* channel;
  struct edge* edge;
  struct network* network;
  FILE *nodes_file, *channels_file, *edges_file;
  char* ret;

  nodes_file = fopen(nodes_filename, "r");
  if(nodes_file==NULL) {
    fprintf(stderr, "ERROR: cannot open file <%s>\n", nodes_filename);
    exit(-1);
  }
  channels_file = fopen(channels_filename, "r");
  if(channels_file==NULL) {
    fprintf(stderr, "ERROR: cannot open file <%s>\n", channels_filename);
    fclose(nodes_file);
    exit(-1);
  }
  edges_file = fopen(edges_filename, "r");
  if(edges_file==NULL) {
    fprintf(stderr, "ERROR: cannot open file <%s>\n", edges_filename);
    fclose(nodes_file);
    fclose(channels_file);
    exit(-1);
  }

  network = (struct network*) malloc(sizeof(struct network));
  network->nodes = array_initialize(1000);
  network->channels = array_initialize(1000);
  network->edges = array_initialize(2000);
  network->partitions = array_initialize(10);

  ret = fgets(row, 2048, nodes_file);
  if(ret == NULL){
    printf("ERROR: cannot read file <%s>\n", nodes_filename);
    fclose(nodes_file);
    fclose(channels_file);
    fclose(edges_file);
    free_network(network);
    exit(-1);
  }

  while(fgets(row, 2048, nodes_file)!=NULL) {
    long intermediary=-1;
    char label[MAXNODELABELSIZE] = "\0";
    char label_country[COUNTRYLABELSIZE] = "\0";
    int partition=-1;
    sscanf(row, "%ld,%30[^,],%30[^,],%d,%ld", &id, label, label_country, &partition,&intermediary);

    enum node_type node_type;
    if(strlen(label) > 2 && !strncmp(label, "CB", 2)){
      node_type = CB;
    } else if (strlen(label) > 12 && !strncmp(label, "Intermediary", 12)){
      node_type = INTERMEDIARY;
    } else if (strlen(label) > 6 && !strncmp(label, "Retail", 6)){
      node_type = END_USER;
    } else if (strlen(label) > 8 && !strncmp(label, "Merchant", 8)){
      node_type = MERCHANT;
    } else {
      // print error message and exit
      printf("ERROR: node type not recognized\n");
      fclose(nodes_file);
      fclose(channels_file);
      fclose(edges_file);
      free_network(network);
      exit(-1);
    }
    node = new_node(id, label, node_type, SMALL, country_string2enum(label_country));
    node->intermediary = intermediary;
    node->partition = force_single_partition ? 0 : partition;
    network->nodes = array_insert(network->nodes, node);

    if(array_len(network->partitions) <= node->partition){
      for(int k=array_len(network->partitions); k<= node->partition; k++){
        network->partitions = array_insert(network->partitions, NULL);
      }
    }
    struct element* nodes_in_partition = array_get(network->partitions, node->partition);
    nodes_in_partition = push(nodes_in_partition, node);
    network->partitions = array_set(network->partitions, node->partition, nodes_in_partition);
  }
  fclose(nodes_file);

  ret = fgets(row, 2048, channels_file);
  if(ret == NULL){
    printf("ERROR: cannot read file <%s>\n", channels_filename);
    fclose(channels_file);
    fclose(edges_file);
    free_network(network);
    exit(-1);
  }
  while(fgets(row, 2048, channels_file)!=NULL) {
    sscanf(row, "%ld,%ld,%ld,%ld,%ld,%ld,%d", &id, &direction1, &direction2, &node_id1, &node_id2, &capacity, &is_private);
    channel = new_channel(id, direction1, direction2, node_id1, node_id2, capacity, is_private);
    network->channels = array_insert(network->channels, channel);
  }
  fclose(channels_file);


  ret = fgets(row, 2048, edges_file);
  if(ret == NULL){
    printf("ERROR: cannot read file <%s>\n", edges_filename);
    fclose(edges_file);
    free_network(network);
    exit(-1);
  }
  while(fgets(row, 2048, edges_file)!=NULL) {
    sscanf(row, "%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%d", &id, &channel_id, &other_direction, &node_id1, &node_id2, &balance, &policy.fee_base, &policy.fee_proportional, &policy.min_htlc, &policy.timelock);
    edge = new_edge(id, channel_id, other_direction, node_id1, node_id2, balance, policy);
    network->edges = array_insert(network->edges, edge);
    node = array_get(network->nodes, node_id1);
    node->open_edges = array_insert(node->open_edges, &(edge->id));
  }
  fclose(edges_file);

  for(int i=0; i<array_len(network->nodes); i++){
    struct node* n = array_get(network->nodes, i);
    if(n->type == END_USER && get_node_wallet_cap(network, n) == 0){
      printf("ERROR: user %d has wallet cap = 0\n", i);
      exit(-1);
    }
  }

  return network;
}

void free_network(struct network* network){
  // nodes
  int n_nodes = array_len(network->nodes);

  for(int i=0; i<n_nodes; i++){
    struct node* node = array_get(network->nodes, i);
    free(node->label);
    free(node->open_edges->element);
    free(node->open_edges);
    /* free results and allocated adjacency list element */
    {
      struct element* iterator, *next;
      for(iterator=node->results; iterator!=NULL;){
        next = iterator->next;
        if (((struct node_list_element *)iterator->data)->edges != NULL){
          list_free(((struct node_list_element *)iterator->data)->edges);
        }
        iterator = next;
      }
      list_free(node->results);
      node->results = NULL;
    }
  }
  array_free(network->nodes);
  // edges
  array_free(network->edges);
  // channels
  array_free(network->channels);
  // network
  free(network);
}

uint64_t get_node_available_balance(struct node* node){
  struct edge* edge;
  uint64_t total_balance = 0;
  for(int i=0; i<array_len(node->open_edges); i++){
    edge = array_get(node->open_edges, i);
    total_balance += edge->balance;
  }
  return total_balance;
}

uint64_t get_node_wallet_cap(struct network* network, struct node* node){
  struct edge* edge;
  struct channel* channel;
  uint64_t total_cap = 0;
  for(int i=0; i<array_len(node->open_edges); i++){
    edge = array_get(node->open_edges, i);
    channel = array_get(network->channels, edge->channel_id);
    total_cap += channel->capacity;
  }
  return total_cap;
}

struct network* initialize_network(char input_dir_name[], unsigned int use_known_paths, int force_single_partition){
  struct network_params net_params;

  // Initialize input paramenters
  strcpy(net_params.nodes_filename, "\0");
  strcpy(net_params.channels_filename, "\0");
  strcpy(net_params.edges_filename, "\0");
  strcpy(net_params.network_filename, "\0");

  // Trim leading /
  while(input_dir_name[strlen(input_dir_name)-1]=='/'){
    input_dir_name[strlen(input_dir_name)-1] = '\0';
  }

  char nodes_filename[PATH_MAX];
  strcpy(nodes_filename, input_dir_name);
  strcat(nodes_filename, "/plasma_network_nodes.csv");
  strcpy(net_params.nodes_filename, nodes_filename);

  char channels_filename[PATH_MAX];
  strcpy(channels_filename, input_dir_name);
  strcat(channels_filename, "/plasma_network_channels.csv");
  strcpy(net_params.channels_filename, channels_filename);

  char edges_filename[PATH_MAX];
  strcpy(edges_filename, input_dir_name);
  strcat(edges_filename, "/plasma_network_edges.csv");
  strcpy(net_params.edges_filename, edges_filename);

  struct network* network = generate_network_from_files(net_params.nodes_filename, net_params.channels_filename, net_params.edges_filename, force_single_partition);

  return  network;
}
