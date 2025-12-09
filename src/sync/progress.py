"""
Base progress tracking for async operations.
"""

import shutil
import sys
import threading
from typing import Optional
from .renderer import get_block_renderer

class ProgressTracker:
    """Base class for thread-safe progress tracking."""

    def __init__(self):
        self.lock = threading.Lock()
        self._closed = False
        self._cancelled = False

        self._block_renderer = get_block_renderer()
        self._active_job_status: Optional[dict] = None

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self):
        """Signal cancellation."""
        self._cancelled = True

    def write(self, msg: str):
        """Write a message (not thread-safe, assumes lock already obtained)."""
        # This will default to a normal print if block rendering is not active
        self._block_renderer.prepend_message(msg)

    def locked_write(self, msg: str):
        """Write a message (thread-safe)."""
        with self.lock:
            # This will default to a normal print if block rendering is not active
            self.write(msg)
    
    def display_new_job(self, total_files: int = 0, total_charts: int = 0):
        self._active_job_status = {
            "total_files": total_files,
            "total_charts": total_charts,
            "charts_completed": 0,
            "concurrent_downloads": 0
        }

        self._block_renderer.set_block_header("title", f"  Downloading {total_files} files across {total_charts} charts... 0% (0/{total_charts})")
        self._block_renderer.set_block_header("active", f"  0 downloads active, totaling 0 MB.")
        self._block_renderer.set_block_header("limits", f"  (max 0 concurrent downloads)")
        self._block_renderer.set_block_header("exit", f"  Press ESC to cancel.")
    
    def update_active_job_status(self, key: str, value: int):
        """Update active job tracking info."""
        status = self._active_job_status

        if key == "concurrent_bytes:":
            key = "concurrent_MB"
            value = value / (1024 * 1024)

        if (status is not None) and (key in status):
            status[key] = value

            if key == "concurrent_downloads":
                self._block_renderer.set_block_header("limits", f"  (max {value} concurrent downloads)")
                return

            total_charts = status["total_charts"]
            charts_completed = status["charts_completed"]
            pct = (charts_completed / total_charts * 100) if total_charts > 0 else 0

            self._block_renderer.set_block_header("title", f"  Downloading {status['total_files']} files across {total_charts} charts... {pct:.1f}% ({charts_completed}/{total_charts})")
            self._block_renderer.set_block_header("active", f"  {status['concurrent_downloads']} downloads active.")

    def display_update(self, key: str, display_name: str, bytes_downloaded: int, total_bytes: int):
        if self._closed:
            return
        
        pct = (bytes_downloaded / total_bytes * 100) if total_bytes > 0 else 0
        size_mb = bytes_downloaded / (1024 * 1024)
        total_mb = total_bytes / (1024 * 1024)

        message_tokens = [
            "  ↓ ",
            f": {size_mb:.0f}/{total_mb:.0f} MB ({pct:.0f}%)"
        ]

        available_columns = shutil.get_terminal_size().columns - len("".join(message_tokens))

        if len(display_name) <= available_columns:
            message_tokens.insert(1, display_name)
        else:
            # Display name is too long, prioritize file name and truncate parent folder if space is still available
            display_name_tokens = display_name.split("/")
            file_name = display_name_tokens[-1]

            if len(file_name) > available_columns:
                # File name alone is too long, prioritize extension
                ext_index = file_name.rfind(".")
                if ext_index == -1:
                    # No extension, just truncate
                    file_name = file_name[:available_columns-3] + "..."
                else:
                    # Truncate while preserving extension
                    file_name = file_name[:available_columns-3-(len(file_name)-ext_index)] + "..." + file_name[ext_index:]
            
            message_tokens.insert(1, file_name)

            if len(display_name_tokens) > 1:
                # There is a parent folder, try to include truncated version
                parent_folder = display_name_tokens[0]
                
                remaining_space = available_columns - len(file_name) - 1  # 1 for the slash

                if len(parent_folder) > remaining_space:
                    parent_folder = parent_folder[:remaining_space-3] + "..."
                
                message_tokens.insert(1, parent_folder + "/")

        self._block_renderer.update_block_item(key, "".join(message_tokens))
    
    def locked_display_update(self, key: str, display_name: str, bytes_downloaded: int, total_bytes: int):
        """Generate a standardized update message (thread-safe)."""
        with self.lock:
            self.display_update(key, display_name, bytes_downloaded, total_bytes)

    def finalize_item(self, key: str, final_msg: str = ""):
        """Removes block rendering item and prepends option message above the block. Caller must hold lock."""
        if self._closed:
            return
        
        self._block_renderer.remove_block_item(key, final_msg)
    
    def locked_finalize_item(self, key: str, final_msg: str = ""):
        """Removes block rendering item and prepends option message above the block. (thread-safe)"""
        with self.lock:
            self.finalize_item(key, final_msg)

    def close(self):
        """Close the progress tracker."""
        with self.lock:
            self._closed = True
            self._active_job_status = None
            self._block_renderer.clear_all()
