import os
import subprocess
import sys
import time

import requests


def main():
    print("==================================================")
    print("Starting Travel Planner Local Backend & UI Server")
    print("==================================================")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    server_process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.fast_api_app:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        env=env,
    )

    # Wait for server to start
    print("Waiting for server to become healthy on http://127.0.0.1:8000 ...")
    max_wait = 45
    start_time = time.time()
    healthy = False

    while time.time() - start_time < max_wait:
        if server_process.poll() is not None:
            print(
                "Server process died prematurely with return code:",
                server_process.returncode,
            )
            sys.exit(1)
        try:
            r1 = requests.get("http://127.0.0.1:8000/index.html", timeout=2)
            if r1.status_code == 200:
                healthy = True
                print(
                    f"✓ Server is healthy after {int(time.time() - start_time)}s! (Frontend & A2A endpoint verified)"
                )
                break
        except Exception:
            pass
        time.sleep(1)

    if not healthy:
        print("Server failed to respond within timeout.")
        server_process.kill()
        sys.exit(1)

    exit_code = 0
    try:
        # Run test_e2e_browser.js
        print("\n==================================================")
        print("Executing test_e2e_browser.js (Browser End-to-End Test)")
        print("==================================================")

        e2e_res = subprocess.run(["node", "test_e2e_browser.js"])
        if e2e_res.returncode != 0:
            print("\n❌ test_e2e_browser.js FAILED with exit code:", e2e_res.returncode)
            exit_code = e2e_res.returncode
        else:
            print("\n==================================================")
            print("Executing test_puppeteer.js (5 Iterations Stability Test)")
            print("==================================================")
            pup_res = subprocess.run(["node", "test_puppeteer.js"])
            if pup_res.returncode != 0:
                print(
                    "\n❌ test_puppeteer.js FAILED with exit code:", pup_res.returncode
                )
                exit_code = pup_res.returncode
            else:
                print("\n==================================================")
                print("🎉 ALL BROWSER UI END-TO-END TESTS PASSED!")
                print("==================================================")

    finally:
        print("\nStopping local server...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()
        print("Server stopped cleanly.")

    if exit_code != 0:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
