"""Judge Service configuration."""

from __future__ import annotations

import os


class JudgeConfig:
    MAX_WORKERS: int = int(os.getenv("JUDGE_MAX_WORKERS", "5"))
    RUN_TIMEOUT_SECONDS: int = int(os.getenv("JUDGE_RUN_TIMEOUT", "10"))
    SUBMIT_TIMEOUT_PER_CASE: int = int(os.getenv("JUDGE_SUBMIT_TIMEOUT_PER_CASE", "5"))
    MEMORY_LIMIT_MB: int = int(os.getenv("JUDGE_MEMORY_LIMIT_MB", "256"))
    CPU_PERIOD: int = 100_000
    CPU_QUOTA: int = 50_000  # 50% of one CPU

    LANGUAGE_IMAGES: dict[str, str] = {
        "python": os.getenv("JUDGE_IMAGE_PYTHON", "interviewiq-python:3.11"),
        "javascript": os.getenv("JUDGE_IMAGE_JS", "interviewiq-node:20"),
        "java": os.getenv("JUDGE_IMAGE_JAVA", "interviewiq-java:21"),
        "cpp": os.getenv("JUDGE_IMAGE_CPP", "interviewiq-cpp:latest"),
        "go": os.getenv("JUDGE_IMAGE_GO", "interviewiq-go:1.22"),
    }

    LANGUAGE_COMMANDS: dict[str, list[str]] = {
        "python": ["python3", "/tmp/solution.py"],
        "javascript": ["node", "/tmp/solution.js"],
        "java": ["sh", "-c", "cd /tmp && javac Solution.java && java Solution"],
        "cpp": ["sh", "-c", "cd /tmp && g++ -o solution solution.cpp && ./solution"],
        "go": ["sh", "-c", "cd /tmp && go run solution.go"],
    }

    LANGUAGE_FILENAMES: dict[str, str] = {
        "python": "solution.py",
        "javascript": "solution.js",
        "java": "Solution.java",
        "cpp": "solution.cpp",
        "go": "solution.go",
    }


config = JudgeConfig()
