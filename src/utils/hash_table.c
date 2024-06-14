#include "hash_table.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

int hash(char* key) {
    int hash_value = 0;
    int len = strlen(key);

    for (int i = 0; i < len; i++) {
        hash_value += key[i];
    }

    return hash_value % TABLE_SIZE;
}

void hash_table_insert(struct hash_table *hash_table[], char* key, void *value) {
    int index = hash(key);

    // Check if the key already exists in the chain
    struct hash_table *current = hash_table[index];
    while (current != NULL) {
        if (strcmp(current->key, key) == 0) {
            // Key already exists, update the value
            current->value = value;
            return;
        }
        current = current->next;
    }

    // Key doesn't exist in the chain, create a new KeyValue pair
    struct hash_table *pair = (struct hash_table *)malloc(sizeof(struct hash_table));
    pair->key = strdup(key); // Copy the key string to avoid sharing memory
    pair->value = value;
    pair->next = hash_table[index];
    hash_table[index] = pair;
}

// Function to retrieve a value from the hash table given a key
void* hash_table_get(struct hash_table *hash_table[], char* key) {
    int index = hash(key);

    // Traverse the chain to find the key
    struct hash_table *current = hash_table[index];
    while (current != NULL) {
        if (strcmp(current->key, key) == 0) {
            return current->value; // Key found, return the value
        }
        current = current->next;
    }

    return NULL; // Key not found
}
