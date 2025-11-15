from __future__ import annotations
import asyncio
import contextlib
import os
import sys
import threading
from typing import AsyncGenerator, Callable, Tuple

from rekuest_next import messages
from rekuest_next.actors.types import Agent
from rekuest_next.api.schema import Assignation


# -------------------------------------------------------
# FD-LEVEL STDOUT + STDERR CAPTURE (works for C/Rust/Python)
# -------------------------------------------------------


@contextlib.asynccontextmanager
async def capture_stdouterr() -> AsyncGenerator[Callable[[], Tuple[str, str]], None]:
    """
    Capture both stdout (fd=1) and stderr (fd=2) at the FD level.

    This captures:
    - Python print()
    - sys.stderr.write()
    - C printf()
    - C fprintf(stderr, ...)
    - Rust println!() and eprintln!()
    - Anything writing to file descriptors 1 and 2.

    Returns:
        A callable get_logs() → (stdout: str, stderr: str)
    """

    # Create pipes for capturing stdout & stderr
    out_r, out_w = os.pipe()
    err_r, err_w = os.pipe()

    # Duplicate original file descriptors
    orig_out = os.dup(1)
    orig_err = os.dup(2)

    # Redirect fd 1 → out_w, fd 2 → err_w
    os.dup2(out_w, 1)
    os.dup2(err_w, 2)

    # Close writer ends (FD now duplicated)
    os.close(out_w)
    os.close(err_w)

    out_chunks: list[bytes] = []
    err_chunks: list[bytes] = []

    # Readers run in background threads because os.read() blocks
    def reader(fd: int, target: list[bytes]) -> None:
        with os.fdopen(fd, "rb") as f:
            while True:
                data = f.read()
                print(f"reader got data: {data!r}", file=sys.__stderr__)
                if not data:
                    break
                target.append(data)

    t_out = threading.Thread(target=reader, args=(out_r, out_chunks))
    t_err = threading.Thread(target=reader, args=(err_r, err_chunks))
    t_out.start()
    t_err.start()

    try:
        # Provide a callable for retrieving the logs
        def get_logs() -> Tuple[str, str]:
            print("get_logs called")
            return (
                b"".join(out_chunks).decode(errors="replace"),
                b"".join(err_chunks).decode(errors="replace"),
            )

        yield get_logs

    finally:
        # Restore original stdout/stderr
        os.dup2(orig_out, 1)
        os.dup2(orig_err, 2)
        os.close(orig_out)
        os.close(orig_err)

        # Ensure threads finish draining the pipes
        t_out.join()
        t_err.join()


@contextlib.asynccontextmanager
async def capture_to_list(
    logs: list[str], agent: Agent, assignment: messages.Assign
) -> AsyncGenerator[None, None]:
    """
    Unified context manager that:
    1. Enforces correct execution semantics (exclusive capture vs concurrent normal)
    2. Captures stdout/stderr at FD level when capture flag is set
    3. Writes captured output DIRECTLY to the provided list in real-time

    - Normal assignments run immediately unless a capture assignment is active.
    - Capture assignments run *exclusively*, blocking all others.
    - Capture assignments capture stdout + stderr at FD level and write directly to logs list.
    - Normal assignments do not capture logs and do not block other normals.

    Parameters
    ----------
    logs : list[str]
        List to append captured output to DIRECTLY as it's captured
    agent : Agent
        Agent with capture_condition and capture_active attributes
    assignment : messages.Assign
        Assignment object with a boolean `.capture` attribute

    Yields
    ------
    None
    """

    should_capture: bool = assignment.capture

    if should_capture:
        # ================================
        #  CAPTURE ASSIGNMENT (exclusive)
        # ================================
        async with agent.capture_condition:
            # Wait if another capture session is active
            while agent.capture_active:
                await agent.capture_condition.wait()

            # Activate capture mode
            agent.capture_active = True

        try:
            # Create pipes for capturing stdout & stderr
            out_r, out_w = os.pipe()
            err_r, err_w = os.pipe()

            # Duplicate original file descriptors
            orig_out = os.dup(1)
            orig_err = os.dup(2)

            # Redirect fd 1 → out_w, fd 2 → err_w
            os.dup2(out_w, 1)
            os.dup2(err_w, 2)

            # Close writer ends (FD now duplicated)
            os.close(out_w)
            os.close(err_w)

            # Reader threads that write DIRECTLY to the logs list
            def reader(fd: int, prefix: str) -> None:
                with os.fdopen(fd, "rb") as f:
                    while True:
                        data = f.read()
                        if not data:
                            break
                        text = data.decode(errors="replace")
                        if text:
                            # Write DIRECTLY to logs list
                            logs.append(text)

            t_out = threading.Thread(target=reader, args=(out_r, "stdout"))
            t_err = threading.Thread(target=reader, args=(err_r, "stderr"))
            t_out.start()
            t_err.start()

            try:
                yield
            finally:
                # Restore original stdout/stderr
                os.dup2(orig_out, 1)
                os.dup2(orig_err, 2)
                os.close(orig_out)
                os.close(orig_err)

                # Ensure threads finish draining the pipes
                t_out.join()
                t_err.join()

        finally:
            # Capture session finished — release the world
            async with agent.capture_condition:
                agent.capture_active = False
                agent.capture_condition.notify_all()

    else:
        # ================================
        #  NORMAL ASSIGNMENT (concurrent)
        # ================================
        async with agent.capture_condition:
            # If a capture task is running, we must wait
            while agent.capture_active:
                await agent.capture_condition.wait()

        # No capture active → proceed normally, allow concurrency
        yield
