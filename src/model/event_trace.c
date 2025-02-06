#include <stdio.h>
#include "event_trace.h"

#include "message.h"

void event_trace(struct message *m, tw_lp *lp, char *buffer, int *collect_flag)
{
  char event_name[128] = "\0";
  const char* result = getEventName(m->type);
  strncpy(event_name, result, sizeof(event_name)-1);
  event_name[127] = '\0';
  strncpy(buffer, event_name, sizeof(event_name));
  memcpy(buffer + 128, &m->computation_time, sizeof(double));
  return;
}
