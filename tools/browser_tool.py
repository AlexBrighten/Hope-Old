"""Browser automation tools — Python wrappers around puppeteer_runner.js."""

import json
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
RUNNER = HERE / "puppeteer_runner.js"
WORKSPACE = HERE


def _check_prereqs() -> str | None:
    """Return an error string if prerequisites are missing, else None."""
    node = shutil.which("node")
    if not node:
        return "Error: Node.js is not installed or not on PATH. Install it from https://nodejs.org"
    puppeteer_dir = HERE / "node_modules" / "puppeteer"
    if not puppeteer_dir.exists():
        return (
            "Error: puppeteer is not installed. Run the following in the Hope directory:\n"
            "  npm install puppeteer"
        )
    if not RUNNER.exists():
        return f"Error: puppeteer_runner.js not found at {RUNNER}"
    return None


def _run(command: str, *args: str, timeout: int = 60) -> str:
    """Execute a puppeteer_runner.js command and return its stdout."""
    prereq_err = _check_prereqs()
    if prereq_err:
        return prereq_err

    node = shutil.which("node")
    cmd = [node, str(RUNNER), command, *args]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(HERE),
        )
        output = result.stdout.strip()
        if result.returncode != 0 and result.stderr:
            return output + "\n[stderr] " + result.stderr.strip() if output else "[stderr] " + result.stderr.strip()
        return output if output else "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout}s"
    except Exception as e:
        return f"Error running puppeteer: {e}"


def browser_open_and_read(url: str, wait_selector: str = "") -> str:
    """Open a URL in a headless browser and return the page's readable text content.

    Args:
        url: The web page URL to open.
        wait_selector: Optional CSS selector to wait for before extracting text.

    Returns:
        The page text content (up to 8000 chars) or an error message.
    """
    if wait_selector:
        # Use interact with a wait action then read final text
        actions = json.dumps([{"action": "wait", "selector": wait_selector}])
        return _run("interact", url, actions)
    return _run("navigate", url)


def browser_take_screenshot(url: str, filename: str = "screenshot.png") -> str:
    """Take a PNG screenshot of a web page.

    Args:
        url: The web page URL to screenshot.
        filename: Output filename (saved in the workspace folder).

    Returns:
        The absolute path to the saved screenshot or an error message.
    """
    output_path = str(WORKSPACE / filename)
    return _run("screenshot", url, output_path)


def browser_interact(url: str, steps_json: str) -> str:
    """Perform a sequence of browser actions on a web page.

    Args:
        url: The web page URL to interact with.
        steps_json: A JSON string array of action objects. Supported actions:
            - {"action": "click", "selector": "button.submit"}
            - {"action": "type", "selector": "input#search", "text": "hello"}
            - {"action": "wait", "selector": ".results"}
            - {"action": "extract", "selector": ".results"}

    Returns:
        Extracted text and final page content, or an error message.
    """
    return _run("interact", url, steps_json)


def browser_capture_api(url: str, api_keyword: str) -> str:
    """Navigate to a URL and capture network API requests matching a keyword.

    Args:
        url: The web page URL to navigate to.
        api_keyword: Substring to match against request URLs (e.g. '/api/').

    Returns:
        JSON array of intercepted requests (url, method, status, body preview) or an error.
    """
    return _run("capture_api", url, api_keyword)


ALL = [
    browser_open_and_read,
    browser_take_screenshot,
    browser_interact,
    browser_capture_api,
]
