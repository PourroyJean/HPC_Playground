CC = cc
CFLAGS = -Wall -Wextra -O2 -I$(HOME)/TOOLS/hwloc/include
LDFLAGS = -lnuma -L$(HOME)/TOOLS/hwloc/lib -lhwloc

TARGET = numa_allocator
SRCS = numa_allocator.c
OBJS = $(SRCS:.c=.o)

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(OBJS) -o $(TARGET) $(LDFLAGS)

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(TARGET) 