"""Docker-based sandboxed code executor."""

from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List

import docker
from docker.errors import ContainerError, ImageNotFound, APIError

from .config import config
from .models import TestCase, TestCaseResult

logger = logging.getLogger(__name__)

_client: docker.DockerClient | None = None
_executor = ThreadPoolExecutor(max_workers=config.MAX_WORKERS)


def get_docker_client() -> docker.DockerClient:
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


def _run_single_case(
    code: str,
    language: str,
    test_case: TestCase,
    timeout: int,
) -> TestCaseResult:
    """Execute code against a single test case inside a Docker container."""
    client = get_docker_client()

    image = config.LANGUAGE_IMAGES.get(language)
    if not image:
        return TestCaseResult(
            input=test_case.input,
            expected_output=test_case.expected_output,
            actual_output="",
            passed=False,
            execution_time_ms=0,
            error=f"Unsupported language: {language}",
            status="RE",
        )

    filename = config.LANGUAGE_FILENAMES[language]
    command = config.LANGUAGE_COMMANDS[language]

    start = time.perf_counter()
    try:
        container = client.containers.run(
            image,
            command=["sh", "-c", f"cat > /tmp/{filename} << 'CODEEOF'\n{code}\nCODEEOF\necho '{test_case.input}' | {' '.join(command)}"],
            detach=True,
            network_disabled=True,
            read_only=False,
            mem_limit=f"{config.MEMORY_LIMIT_MB}m",
            cpu_period=config.CPU_PERIOD,
            cpu_quota=config.CPU_QUOTA,
            tmpfs={"/tmp": "rw,noexec,nosuid,size=64m"},
            stdin_open=False,
        )

        try:
            result = container.wait(timeout=timeout)
            exit_code = result.get("StatusCode", -1)
            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace").strip()
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace").strip()
        except Exception:
            container.kill()
            elapsed = (time.perf_counter() - start) * 1000
            return TestCaseResult(
                input=test_case.input,
                expected_output=test_case.expected_output,
                actual_output="",
                passed=False,
                execution_time_ms=elapsed,
                error="Time Limit Exceeded",
                status="TLE",
            )
        finally:
            container.remove(force=True)

        elapsed = (time.perf_counter() - start) * 1000
        actual = stdout.strip()
        expected = test_case.expected_output.strip()
        passed = actual == expected

        error_msg = stderr if exit_code != 0 else None

        return TestCaseResult(
            input=test_case.input,
            expected_output=test_case.expected_output,
            actual_output=actual,
            passed=passed,
            execution_time_ms=round(elapsed, 2),
            error=error_msg,
            status="ok" if exit_code == 0 else "RE",
        )

    except ImageNotFound:
        elapsed = (time.perf_counter() - start) * 1000
        return TestCaseResult(
            input=test_case.input,
            expected_output=test_case.expected_output,
            actual_output="",
            passed=False,
            execution_time_ms=elapsed,
            error=f"Language image '{image}' not found. Run build_images script first.",
            status="RE",
        )
    except (ContainerError, APIError) as e:
        elapsed = (time.perf_counter() - start) * 1000
        return TestCaseResult(
            input=test_case.input,
            expected_output=test_case.expected_output,
            actual_output="",
            passed=False,
            execution_time_ms=elapsed,
            error=str(e),
            status="RE",
        )


async def execute_code(
    code: str,
    language: str,
    test_cases: List[TestCase],
    timeout: int | None = None,
) -> List[TestCaseResult]:
    """Run code against all test cases concurrently."""
    per_case_timeout = timeout or config.SUBMIT_TIMEOUT_PER_CASE
    loop = asyncio.get_event_loop()

    tasks = [
        loop.run_in_executor(
            _executor,
            _run_single_case,
            code,
            language,
            tc,
            per_case_timeout,
        )
        for tc in test_cases
    ]

    return list(await asyncio.gather(*tasks))
