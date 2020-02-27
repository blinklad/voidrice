#pragma once

#include <stdlib.h>
#include <stdio.h>

typedef struct listNode
{
	void *data;
	struct listNode *next;
} *ListNodePtr;

typedef struct list
{
	ListNodePtr head;
} List;

List
new_list();

void
insert_at_front(List self, void *data);

void
insert_at_rear(List self, void *data);

void
insert_at_rear(List self, void *data);

void
destroy_list(List self, void *data);
