import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from click.testing import CliRunner

from src.cli import cli
from src.db import crud
from src.db.database import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


def test_init_db():
    r = CliRunner().invoke(cli, ["init-db"])
    assert r.exit_code == 0, r.output
    assert "users" in r.output


def test_create_and_list_users():
    suffix = _suffix()
    username = f"cli_{suffix}"
    email = f"{suffix}@cli.dev"
    runner = CliRunner()
    r = runner.invoke(
        cli,
        [
            "create-user",
            "--email",
            email,
            "--username",
            username,
            "--password",
            "hunter22",
        ],
    )
    assert r.exit_code == 0, r.output
    r = runner.invoke(cli, ["list-users"])
    assert r.exit_code == 0, r.output
    assert username in r.output


def test_create_user_duplicate_conflict():
    suffix = _suffix()
    args = [
        "create-user",
        "--email",
        f"{suffix}@cli.dev",
        "--username",
        f"cli_{suffix}",
        "--password",
        "hunter22",
    ]
    runner = CliRunner()
    assert runner.invoke(cli, args).exit_code == 0
    assert runner.invoke(cli, args).exit_code != 0


def test_upload_and_list_datasets():
    suffix = _suffix()
    name = f"cli_ds_{suffix}"
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("sample.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        r = runner.invoke(cli, ["upload-dataset", "--file", "sample.csv", "--name", name])
        assert r.exit_code == 0, r.output
        assert name in r.output
    r = runner.invoke(cli, ["list-datasets"])
    assert r.exit_code == 0, r.output
    assert name in r.output


def test_upload_bad_extension_rejected():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("bad.xlsx").write_bytes(b"x")
        r = runner.invoke(cli, ["upload-dataset", "--file", "bad.xlsx"])
        assert r.exit_code != 0


def test_train_stub_exits_nonzero():
    suffix = _suffix()
    db = SessionLocal()
    try:
        users = crud.get_users(db, limit=1)
        if not users:
            crud.create_user(
                db,
                email=f"t_{suffix}@x.dev",
                username=f"t_{suffix}",
                password="hunter22",
            )
            users = crud.get_users(db, limit=1)
        ds = crud.create_dataset(
            db,
            {"name": f"train_{suffix}", "storage_uri": "stub://x", "format": "csv"},
            users[0].id,
        )
        ds_id = ds.id
    finally:
        db.close()
    r = CliRunner().invoke(
        cli,
        [
            "train",
            "--dataset-id",
            str(ds_id),
            "--target",
            "target_col",
            "--experiment",
            f"exp_{suffix}",
        ],
    )
    assert r.exit_code == 1
    assert "not implemented" in r.output.lower()


def test_status_ok():
    r = CliRunner().invoke(cli, ["status"])
    assert r.exit_code == 0, r.output
    assert "users" in r.output.lower()


def test_module_entrypoint_help():
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "-m", "src.cli", "--help"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert "init-db" in proc.stdout
