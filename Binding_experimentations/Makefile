CC = cc
HWLOC_DIR ?= $(HOME)/TOOLS/hwloc
CFLAGS = -Wall -Wextra -O2 -I$(HWLOC_DIR)/include
LDFLAGS = -lnuma -L$(HWLOC_DIR)/lib -lhwloc

TARGET = numa_bench
SRCS = numa_bench.c
OBJS = $(SRCS:.c=.o)

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(OBJS) -o $(TARGET) $(LDFLAGS)

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(TARGET) 