"""
    Note: All times are in millisecond.
"""
import argparse
import json
import shlex
import sys
from collections import namedtuple
from subprocess import Popen, TimeoutExpired
from time import perf_counter

IDLENESS_LIMIT_EXCEEDED = "Idleness Limit Exceeded"
RUNTIME_ERROR = "Runtime Error"
MEMORY_LIMIT_EXCEEDED = "Memory Limit Exceeded"
TIME_LIMIT_EXCEEDED = "Time Limit Exceeded"
ACCEPTED = "Accepted"


def result(verdict, time_used, memory_used):
    return {
        'verdict': verdict,
        'time_used': time_used,
        'memory_used': memory_used
    }


def run(args):
    input_file = open(args.input)
    output_file = open(args.output, 'w')

    start = perf_counter()
    proc = Popen(shlex.split(args.command),
                 stdin=input_file, stdout=output_file)

    try:
        proc.wait(timeout=args.timelimit / 1000)
        # Convert to milliseconds
        time_elapsed = int((perf_counter() - start) * 1000)
        out, err = proc.communicate()
        print(err, file=sys.stderr)

        if proc.returncode != 0:
            return result(RUNTIME_ERROR, time_elapsed, 0)

    except TimeoutExpired:
        proc.kill()
        return result(TIME_LIMIT_EXCEEDED, args.timelimit, 0)

    return result(ACCEPTED, time_elapsed, 0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser("Simple grader")

    parser.add_argument('-c', '--command', required=True,
                        help="Command to execute")
    parser.add_argument('-i', '--input', required=True, help='Input file')
    parser.add_argument('-o', '--output', required=True,
                        help='Output file')
    parser.add_argument('-t', '--timelimit', default=1000,
                        type=int, help='Time in milliseconds')
    parser.add_argument('-m', '--memorylimit', default=1024 *
                        1024, type=int, help='Memory in bytes')

    args = parser.parse_args()

    result = run(args)
    print(json.dumps(result))
