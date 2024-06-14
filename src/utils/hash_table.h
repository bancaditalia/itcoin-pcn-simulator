#ifndef HASH_TABLE_H
#define HASH_TABLE_H

#define TABLE_SIZE 100

struct hash_table {
    char *key;
    void* value;
    struct hash_table *next;
};

void hash_table_insert(struct hash_table *hash_table[], char *key, void *value);
void* hash_table_get(struct hash_table *hash_table[], char *key);

#endif
