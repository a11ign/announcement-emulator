"""Run a command so that everything it starts can be ended with it (A11-165). Standard library only."""
import os, signal, subprocess

TIMED_OUT = 124      # as timeout(1)


def run_in_group(command, timeout, env=None):
    """Run a command in a process group of its own; when it runs past `timeout` the whole group is killed (the emulator, its session and its Chrome), then TimeoutExpired is raised. Killing only the command would leave
    its children holding the ports of the slot they ran in, and every later run in the slot would fail the moment it started."""
    process = subprocess.Popen(command, start_new_session=True, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try: return process.wait(timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL); process.wait(); raise
