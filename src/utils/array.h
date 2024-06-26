#ifndef ARRAY_H
#define ARRAY_H

struct array {
  void **element;
  long size;
  long index;
};

struct array* array_initialize(long size);

struct array*  array_insert(struct array* a, void* data);

struct array* array_set(struct array* a,long i, void* data);

void* array_get(struct array* a,long i);

long array_len(struct array* a);

void array_reverse(struct array* a);

void array_delete_element(struct array *a, long element_index);

void array_delete_element_nofree(struct array *a, long element_index);

void array_delete(struct array* a, void* element,  int(*is_equal)(void*, void*));

void array_delete_all(struct array* a);

void array_free(struct array* a);

#endif
