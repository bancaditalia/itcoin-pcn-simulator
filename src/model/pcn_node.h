//The header file template for a ROSS model
//This file includes:
// - the state and message structs
// - extern'ed command line arguments
// - custom mapping function prototypes (if needed)
// - any other needed structs, enums, unions, or #defines

#ifndef _model_h
#define _model_h

#include <ross.h>

#include "message.h"
#include "../features/network.h"

#define INF UINT64_MAX

//Command Line Argument declarations
extern unsigned int setting_1;

//Global variables used by both main and driver
// - this defines the LP types
extern tw_lptype model_lps[];

//Function Declarations
// defined in model_driver.c:
// LP - Users
extern void model_init(node *s, tw_lp *lp);
extern void model_event(node *s, tw_bf *bf, message *in_msg, tw_lp *lp);
extern void model_commit(node *s, tw_bf *bf, message *in_msg, tw_lp *lp);
extern void model_event_reverse(node *s, tw_bf *bf, message *in_msg, tw_lp *lp);
extern void model_final(node *s, tw_lp *lp);

// defined in model_map.c:
extern tw_peid model_map(tw_lpid gid);


//Custom mapping prototypes
void model_custom_mapping(void);
tw_lp * model_mapping_to_lp(tw_lpid lpid);
tw_peid model_map(tw_lpid gid);

//Custom mapping prototypes
//tw_lpid metis_typemap (tw_lpid gid);
void metis_custom_mapping(void);
tw_lp * metis_mapping_to_lp(tw_lpid lpid);
tw_peid metis_map(tw_lpid gid);

tw_lpid model_typemap (tw_lpid gid);
#endif
