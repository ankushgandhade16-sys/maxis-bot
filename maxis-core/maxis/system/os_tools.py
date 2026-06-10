"""
OS Tools — Safe shell execution and system statistics.
"""

import subprocess
import psutil
import httpx
import re
from loguru import logger

def get_system_stats() -> dict:
    """Get current system CPU, memory, and disk usage."""
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu_percent": cpu,
            "memory_percent": mem.percent,
            "memory_used_gb": round(mem.used / (1024**3), 2),
            "memory_total_gb": round(mem.total / (1024**3), 2),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / (1024**3), 2)
        }
    except Exception as e:
        logger.error(f"Failed to get system stats: {e}")
        return {"error": str(e)}

def execute_command(command: str) -> str:
    """Execute a shell command with a timeout."""
    logger.warning(f"Executing shell command: {command}")
    try:
        # We run the command with a 10 second timeout to prevent hanging
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10.0
        )
        
        output = result.stdout.strip()
        error = result.stderr.strip()
        
        if result.returncode == 0:
            return output if output else "Command executed successfully (no output)."
        else:
            return f"Command failed with exit code {result.returncode}.\nError:\n{error}\nOutput:\n{output}"
    except subprocess.TimeoutExpired:
        return "Command timed out after 10 seconds."
    except Exception as e:
        logger.error(f"Failed to execute command: {e}")
        return f"Execution error: {e}"

def fetch_url(url: str) -> str:
    """Fetch the text content of a URL."""
    logger.info(f"Fetching URL: {url}")
    try:
        headers = {
            "User-Agent": "MaxisBot/1.0 (https://github.com/ankushgandhade16-sys/maxis-bot) httpx/0.25.0"
        }
        with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
            
            # Simple heuristic: if it's JSON, return it formatted
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                return response.text
                
            # Parse HTML if it's a web page
            if "text/html" in content_type:
                html = response.text
                html = re.sub(r'<(script|style).*?>.*?</\1>', '', html, flags=re.IGNORECASE | re.DOTALL)
                text = re.sub(r'<[^>]+>', ' ', html)
                text = re.sub(r'\s+', ' ', text).strip()
            else:
                text = response.text

            if len(text) > 4000:
                text = text[:4000] + "\n... (truncated)"
            return text
    except httpx.TimeoutException:
        return f"Failed to fetch {url}: Request timed out."
    except Exception as e:
        logger.error(f"Failed to fetch url: {e}")
        return f"Failed to fetch {url}: {e}"



def search_web(query: str, max_results: int = 5) -> str:
    """Search the internet using DuckDuckGo."""
    logger.info(f"Searching web for: {query}")
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            
            if not results:
                return "No results found."
                
            formatted = []
            for i, r in enumerate(results):
                formatted.append(f"Result {i+1}:\nTitle: {r.get('title')}\nURL: {r.get('href')}\nSnippet: {r.get('body')}\n")
                
            return "\n".join(formatted)
    except ImportError:
        return "Failed to search: duckduckgo-search package is not installed."
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return f"Failed to search web: {e}"
