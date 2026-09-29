#!/bin/sh
# Prepares the container's control groups for isolate (see isolate.cf): each
# run gets its own cgroup under /sys/fs/cgroup/isolate, which is how isolate
# limits memory and measures time. Run once when the grader container starts.
#
# Needs the grader container to have SYS_ADMIN and no AppArmor confinement:
# Docker mounts /sys/fs/cgroup read-only, and its AppArmor profile forbids
# the remount (and the mounts isolate makes for every box).
set -e

cgroup=/sys/fs/cgroup

if grep -q " $cgroup cgroup2 ro" /proc/mounts; then
	# Type and source spelled out: busybox's mount can fail to look them up.
	mount -t cgroup2 -o remount,rw,nosuid,nodev,noexec cgroup "$cgroup"
fi

# cgroup v2 lets a cgroup hand controllers down to its children only while it
# has no processes of its own, so move everything out of the container's root
# cgroup into a leaf first.
mkdir -p "$cgroup/grader" "$cgroup/isolate"
for pid in $(cat "$cgroup/cgroup.procs"); do
	echo "$pid" > "$cgroup/grader/cgroup.procs" 2>/dev/null || true
done

# isolate limits memory through memory.max in each box's cgroup.
echo "+memory" > "$cgroup/cgroup.subtree_control"
echo "+memory" > "$cgroup/isolate/cgroup.subtree_control"
