import os
import subprocess
from pathlib import Path


def test_demo_stop_does_not_kill_process_when_pid_metadata_is_stale(tmp_path: Path) -> None:
    sleeper = subprocess.Popen(["sleep", "30"])
    try:
        (tmp_path / "pids").write_text(
            f"backend\t{sleeper.pid}\tstale start time\t0:0\n",
            encoding="utf-8",
        )
        root = Path(__file__).resolve().parents[3]
        environment = {
            **os.environ,
            "DEMO_RUNTIME_DIR": str(tmp_path),
            "DEMO_SKIP_DOCKER_STOP": "true",
        }

        result = subprocess.run(
            [str(root / "scripts" / "stop_demo.sh")],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )

        assert "demo stopped" in result.stdout.lower()
        assert sleeper.poll() is None
        assert not (tmp_path / "pids").exists()
    finally:
        sleeper.terminate()
        sleeper.wait(timeout=5)
