//The C mapping for a ROSS model
//This file includes:
// - the LPType map (when there multiple LP types)
// - the set of custom mapping functions:
//   - setup function to place LPs and KPs on PEs
//   - local map function to find LP in local PE's array

#include <ross.h>

#include "global.h"
#include "pcn_node.h"
#include "event_trace.h"

#include "../features/network.h"

#include "../utils/array.h"
#include "../utils/list.h"


extern unsigned int nkp_per_pe;
//This function maps LPs to KPs on PEs and is called at the start
void metis_custom_mapping(void){
  tw_pe *pe;
  int nlp_per_kp;
  int lp_id, kp_id;
  int i, j;

  // Map the KPs on this PE
  for(kp_id=0; kp_id < nkp_per_pe; kp_id++)
    tw_kp_onpe(kp_id, g_tw_pe);

  // Map the PCN nodes on PE and KP, with type model_lps[0]
  struct element* node_list = array_get(network->partitions, g_tw_mynode);
  i = 0;
  while(node_list != NULL){
    struct node* node = node_list->data;
    kp_id = i % g_tw_nkp;
    node->local_id = i;
    long id = node->id;
    tw_lp_onpe(i, g_tw_pe, id);
    tw_lp_onkp(g_tw_lp[i], g_tw_kp[kp_id]);
    tw_lp_settype(i, &model_lps[0]);
    st_model_settype(i, &model_types[0]);
    node_list = node_list->next;
    i++;
  }

  // Map the Blockchain on KP0 and PE0 with type model_lps[1]
  if(g_tw_mynode==0){
    tw_lp_onpe(i, g_tw_pe, blockchain_lp_gid);
    tw_lp_onkp(g_tw_lp[i], g_tw_kp[0]);
    tw_lp_settype(i, &model_lps[1]);
    st_model_settype(i, &model_types[0]);
  }

  //Error checks for the mapping
  if (!g_tw_lp[g_tw_nlp - 1]) {
    tw_error(TW_LOC, "Not all LPs defined! (g_tw_nlp=%d)", g_tw_nlp);
  }
}

//Given a gid, return the local LP (global id => local id mapping)
tw_lp * metis_mapping_to_lp(tw_lpid gid){
  int index;

  if(gid < array_len(network->nodes)){
    struct node* node = array_get(network->nodes, gid);
    index = node->local_id;
  }
  else if(gid == blockchain_lp_gid){
    // This is the blockchain
    index = nlp_user_per_pe;
  }

  return g_tw_lp[index];
}

//Given an LP's GID (global ID)
//return the PE (aka node, MPI Rank)
tw_peid metis_map(tw_lpid gid){
  int rank;

  if(gid < array_len(network->nodes)){
    struct node* node = array_get(network->nodes, gid);
    rank = node->partition;
  }
  else if (gid == blockchain_lp_gid){
    // This is the blockchain that is always at rank 0
    rank = 0;
  }
  else {
    printf("\n Invalid LP ID %d given for PCN nodes mapping ", (int)gid);
    exit(-1);
  }
  return rank;
}

