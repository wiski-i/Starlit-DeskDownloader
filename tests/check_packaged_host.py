"""Exercise an actual source or frozen Chrome host with binary framing."""
import json
import struct
import subprocess
import sys


def check_host(command: list[str]) -> None:
    payload = json.dumps({"action": "get_profiles"}).encode("utf-8")
    process = subprocess.run(
        command, input=struct.pack("<I", len(payload)) + payload,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45,
    )
    if process.returncode:
        raise AssertionError(f"Host exited with {process.returncode}: {process.stderr.decode(errors='replace')}")
    output = process.stdout
    if len(output) < 4:
        raise AssertionError(f"Missing native header: {output!r}; stderr={process.stderr!r}")
    size, = struct.unpack("<I", output[:4])
    if len(output) != size + 4:
        raise AssertionError(f"Protocol stdout contains missing or extra bytes: {len(output)} vs {size + 4}")
    response = json.loads(output[4:].decode("utf-8"))
    assert response["status"] == "profiles", response
    assert len(response["formats"]) == 15, response
    assert sum(len(item["qualities"]) for item in response["formats"]) == 58, response
    print("Native Messaging framing OK: 15 formats, 58 quality options; stdout is clean.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python tests/check_packaged_host.py HOST [HOST_ARGUMENT ...]")
    check_host(sys.argv[1:])
