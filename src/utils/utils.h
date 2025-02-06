#ifndef UTILS_H
#define UTILS_H
#include <stdbool.h>

#include "../features/routing.h"

struct node_pair_result;

int is_equal_result(struct node_pair_result *a, struct node_pair_result *b);

int is_equal_key_result(long key, struct node_pair_result *a);

int is_equal_node_list_element(long key, struct node_list_element *a);

int is_equal_long(long* a, long* b);

int is_present(long element, struct array* long_array);

int is_key_equal(struct distance* a, struct distance* b);

void free_data_structures(struct network* network, struct array* payments);

bool is_regular_file(const char *path);

void write_output(struct network* network, struct array* payments, char output_dir_name[], unsigned long pe_id);

void initialize_input_parameters(struct network_params *net_params);

#endif
