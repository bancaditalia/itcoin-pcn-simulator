#ifndef _event_trace_h
#define _event_trace_h

#include <ross.h>

extern st_model_types model_types[];

struct message;

typedef struct event_model_data {
    char event_name[128];
    double computation_time;
} event_model_data;

void event_trace(struct message *m, tw_lp *lp, char *buffer, int *collect_flag);

#endif
