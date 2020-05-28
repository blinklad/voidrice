CC = gcc
CFLAGS = -std=c99 -g -Wall -I$(HDIR)

TARGET = run

LINKER   = gcc -o
# linking flags here
LFLAGS   = -Wall -I. -lm

# change these to set the proper directories where each files shoould be
SRCDIR   = src
OBJDIR   = obj
HDIR = include
BINDIR   = bin

SOURCES  := $(wildcard $(SRCDIR)/*.c)
INCLUDES := $(wildcard $(HDIR)/*.h)
OBJECTS  := $(SOURCES:$(SRCDIR)/%.c=$(OBJDIR)/%.o)
rm       = rm -f


$(BINDIR)/$(TARGET): $(OBJECTS)
	@$(LINKER) $@ $(LFLAGS) $(OBJECTS)
	@echo "Linking complete!"

$(OBJECTS): $(OBJDIR)/%.o : $(SRCDIR)/%.c
	@$(CC) $(CFLAGS) -c $< -o $@
	@echo "Compiled "$<" successfully!"

run:
	@gdb -tui $(BINDIR)/$(TARGET)

memcheck:
	@valgrind --leak--check=full $(BINDIR)/$(TARGET)

clean:
	@rm -f $(wildcard $(OBJDIR)/*.o)
	@rm -f $(wildcard $(BINDIR)/*)
	@echo "Cleaned up junk!"
