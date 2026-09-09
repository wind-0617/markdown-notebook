"""执行器基类与注册表：新增语言只需继承 BaseExecutor 并注册（NFR-03 可扩展性）。"""
from __future__ import annotations

import abc
import os
import shlex
import subprocess
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Optional

DEFAULT_TIMEOUT = int(os.environ.get("EXEC_TIMEOUT", "30"))
# 执行工作目录根（默认系统临时目录；生产可指向 tmpfs，测试环境可指向工作区）
EXEC_TMP_ROOT = os.environ.get("EXEC_TMP_DIR", "").strip() or None


@dataclass
class ExecutionResult:
    """一次代码执行的结构化结果。"""

    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    duration_ms: int = 0
    timed_out: bool = False
    language: str = ""
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class BaseExecutor(abc.ABC):
    """所有语言执行器的基类。

    子类只需声明 ``language`` / ``file_ext`` 并实现 ``build_command``；
    超时控制、临时文件、错误封装等由基类统一完成。
    """

    language: str = ""
    file_ext: str = ".txt"
    default_timeout: int = DEFAULT_TIMEOUT

    # ---- 子类实现 -------------------------------------------------
    @abc.abstractmethod
    def build_command(self, script_path: str) -> list[str]:
        """返回执行脚本文件的命令行（local 模式）。"""

    # ---- 公共能力 -------------------------------------------------
    def run(
        self,
        code: str,
        timeout: Optional[int] = None,
        mode: str = "local",
        docker_image: str = "",
        memory_limit: str = "256m",
        cpu_limit: str = "0.5",
    ) -> ExecutionResult:
        """执行一段代码，永远返回 ExecutionResult，不向外抛异常。"""
        if not code or not code.strip():
            return ExecutionResult(
                stderr="代码为空，未执行。", language=self.language
            )
        timeout = min(max(int(timeout or self.default_timeout), 1), 120)

        tmp_dir = self._make_workdir()
        script_path = os.path.join(tmp_dir, f"main{self.file_ext}")
        start = time.perf_counter()
        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            if mode == "docker":
                argv = self._docker_command(
                    script_path, tmp_dir, docker_image, memory_limit, cpu_limit
                )
            else:
                argv = self.build_command(script_path)

            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmp_dir,
                env=self._sandbox_env(tmp_dir),
            )
            elapsed = int((time.perf_counter() - start) * 1000)
            return ExecutionResult(
                stdout=proc.stdout or "",
                stderr=proc.stderr or "",
                exit_code=proc.returncode,
                duration_ms=elapsed,
                language=self.language,
            )
        except subprocess.TimeoutExpired:
            elapsed = int((time.perf_counter() - start) * 1000)
            return ExecutionResult(
                stderr=f"执行超时（>{timeout}s），进程已终止。",
                duration_ms=elapsed,
                timed_out=True,
                language=self.language,
            )
        except FileNotFoundError as exc:
            return ExecutionResult(
                stderr=f"找不到解释器，请确认已安装并加入 PATH：{exc}",
                language=self.language,
            )
        except Exception as exc:  # noqa: BLE001 兜底，保证 API 稳定返回
            return ExecutionResult(
                stderr=f"执行器内部错误：{exc.__class__.__name__}: {exc}",
                language=self.language,
            )
        finally:
            self._cleanup(tmp_dir, script_path)

    # ---- 内部工具 -------------------------------------------------
    @staticmethod
    def _make_workdir() -> str:
        """创建一次性工作目录。

        不用 tempfile.mkdtemp：它会给目录加受限 ACL，在某些受限环境
        （只允许工作区写入的进程沙箱）中反而阻止自己写入脚本文件。
        """
        root = EXEC_TMP_ROOT or tempfile.gettempdir()
        for _ in range(5):
            d = os.path.join(root, f"mnb-{uuid.uuid4().hex[:12]}")
            try:
                os.makedirs(d, exist_ok=False)
                return d
            except FileExistsError:
                continue
        raise RuntimeError("无法创建执行工作目录")

    def _docker_command(
        self,
        script_path: str,
        tmp_dir: str,
        image: str,
        memory_limit: str,
        cpu_limit: str,
    ) -> list[str]:
        """把 local 命令包装为一次性 Docker 沙箱容器（NFR-01）。"""
        inner = " ".join(
            shlex.quote(a)
            for a in self.build_command(f"/sandbox/main{self.file_ext}")
        )
        return [
            "docker", "run", "--rm",
            "--memory", memory_limit,
            "--cpus", str(cpu_limit),
            "--network", "none",               # 沙箱断网
            "--read-only",
            "--tmpfs", "/tmp:rw,size=32m",
            "-v", f"{tmp_dir}:/sandbox:ro",
            image,
            "sh", "-c", inner,
        ]

    @staticmethod
    def _sandbox_env(tmp_dir: str) -> dict:
        env = os.environ.copy()
        # 限制产物只能写入临时目录
        env["TMPDIR"] = tmp_dir
        env["TEMP"] = tmp_dir
        env["TMP"] = tmp_dir
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env

    @staticmethod
    def _cleanup(tmp_dir: str, script_path: str) -> None:
        """尽量回收工作目录；脚本若产生了其他产物也一并删除。"""
        import shutil

        shutil.rmtree(tmp_dir, ignore_errors=True)
        if os.path.exists(script_path):  # 极端情况：目录名冲突等
            try:
                os.remove(script_path)
            except OSError:
                pass


# ------------------------------------------------------------------
# 注册表：语言名 -> 执行器实例
# ------------------------------------------------------------------
_REGISTRY: dict[str, BaseExecutor] = {}


def register(executor: BaseExecutor) -> None:
    _REGISTRY[executor.language] = executor


def get_executor(language: str) -> Optional[BaseExecutor]:
    return _REGISTRY.get((language or "").strip().lower())


def supported_languages() -> list[str]:
    return sorted(_REGISTRY)
