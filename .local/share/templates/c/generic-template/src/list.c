#include <stdlib.h>
#include <stdio.h>
#include "list.h"

List
new_list()
{
	List new;
	new.head = NULL;
	return new;
}

void
insert_at_front(List self, void *data);

void
insert_at_rear(List self, void *data);

void
insert_at_rear(List self, void *data);

void
destroy_list(List self, void *data);
