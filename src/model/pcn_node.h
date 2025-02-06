//The header file template for a ROSS model
//This file includes:
// - the state and message structs
// - custom mapping function prototypes (if needed)
// - any other needed structs, enums, unions, or #defines

#ifndef _model_h
#define _model_h

#include <ross.h>


#define INF UINT64_MAX

struct message;
struct node;

//Global variables used by both main and driver
// - this defines the LP types
extern tw_lptype model_lps[];

//Function Declarations
// defined in model_driver.c:
// LP - Users
extern void model_init(struct node *s, tw_lp *lp);
extern void model_event(struct node *s, tw_bf *bf, struct message *in_msg, tw_lp *lp);
extern void model_commit(struct node *s, tw_bf *bf, struct message *in_msg, tw_lp *lp);
extern void model_event_reverse(struct node *s, tw_bf *bf, struct message *in_msg, tw_lp *lp);
extern void model_final(struct node *s, tw_lp *lp);


//Custom mapping prototypes
void metis_custom_mapping(void);
tw_lp * metis_mapping_to_lp(tw_lpid lpid);
tw_peid metis_map(tw_lpid gid);

#endif
