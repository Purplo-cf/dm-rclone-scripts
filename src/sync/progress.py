"""
Base progress tracking for async operations.
"""

import shutil
import threading

class ProgressTracker:
    """Base class for thread-safe progress tracking."""

    def __init__(self):
        self.lock = threading.Lock()
        self._closed = False
        self._cancelled = False

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self):
        """Signal cancellation."""
        self._cancelled = True

    def write(self, msg: str):
        """Write a message (thread-safe)."""
        with self.lock:
            print(msg)

    def display_update(self, display_name: str, bytes_downloaded: int, total_bytes: int):
        """Generate a standardized update message (thread-safe)."""
        with self.lock:
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

            print("".join(message_tokens))

    def close(self):
        """Close the progress tracker."""
        with self.lock:
            self._closed = True
