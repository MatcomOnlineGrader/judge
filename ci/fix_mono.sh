#!/bin/bash
# Seems like the musl version in alpine:3.15.0 is missing the symbol pthread_getname_np
# It is solved by upgrading to alpine:3.16.0, but that will break dependencies that rely on
# python 3.9, so this simple program solves the issue:

function gen_wrapper() {
	name=$1
	cat << END
#!/bin/sh
export LD_PRELOAD=/fixmono.so
$name \$*
END
}


cat > /tmp/pthread_getname_np.c << EOF

#define _GNU_SOURCE
#include <fcntl.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>
#include <sys/prctl.h>
#include <pthread.h>
#include <errno.h>

int pthread_getname_np(pthread_t thread, char *name, size_t len)
{
        int fd, cs, status = 0;
        char f[sizeof "/proc/self/task//comm" + 3*sizeof(int)];

        if (len > 15) return ERANGE;

        if (thread == pthread_self())
                return prctl(PR_GET_NAME, name) ? errno : 0;

        snprintf(f, sizeof f, "/proc/self/task/%d/comm", (pid_t)thread);
        pthread_setcancelstate(PTHREAD_CANCEL_DISABLE, &cs);
        if ((fd = open(f, O_RDONLY)) < 0 || read(fd, name, len) < 0) status = errno;
        if (fd >= 0) close(fd);
        pthread_setcancelstate(cs, 0);
        return status;
}

EOF

# Compile and save
gcc -shared /tmp/pthread_getname_np.c -o /fixmono.so

# Generate the wrapper script(s)
gen_wrapper /usr/bin/csc > /usr/local/bin/csc
gen_wrapper /usr/bin/mono > /usr/local/bin/mono
chmod +x /usr/local/bin/csc
chmod +x /usr/local/bin/mono
