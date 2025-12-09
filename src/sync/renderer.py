"""
Centralized console rendering for all async operations.

Coordinates all console output (messages and progress blocks) to prevent
rendering conflicts when multiple sources write to stdout concurrently.
"""

import sys
import os
import time

from typing import Optional

# Simple ANSI capability detection (Windows 10+ usually fine)
_ANSI_ENABLED = True
if os.name == 'nt':
	if os.environ.get('NO_ANSI', ''):
		_ANSI_ENABLED = False


class BlockRenderer:
	"""
	Centralized console renderer that coordinates all stdout output.
	
	Handles:
	- Regular message printing (from any source)
	- Multi-line progress block rendering (from progress trackers)
	- Proper clearing/re-rendering when messages interrupt progress blocks
	"""

	HEADER_SEPARATOR = "=" * 50

	def __init__(self):
		# Progress block state (populated by progress trackers)
		self.block_rendering = False

		self._block_header: dict[str, str] = {}
		self._block_items: dict[str, str] = {}
		self._block_reserved_lines = 0
		
		# Fallback throttling when ANSI unavailable
		self._last_prints: dict[str, tuple[str, float]] = {}

	def set_block_header(self, key: str, msg: str = None):
		"""Set or clear the progress block header."""
		if msg:
			self._block_header[key] = msg
		else:
			if key in self._block_header:
				del self._block_header[key]
	
	def update_block_item(self, key: str, msg: str):
		"""Add or update a progress item in the rendered block."""
		if self._block_items.get(key) != msg: # Only update if changed
			self._block_items[key] = msg
			
			if not _ANSI_ENABLED:
				# Fallback: print with throttling
				now = time.time()
				last = self._last_prints.get(key)
				if last is None or (msg != last[0] and (now - last[1]) >= 1.5):
					print(msg)
					self._last_prints[key] = (msg, now)
				return
			
			self._render_block()

	def remove_block_item(self, key: str, prepend_msg: str = ""):
		"""Remove progress item from block and re-render."""
		# Clear fallback state
		if key in self._last_prints:
			del self._last_prints[key]
		
		if key in self._block_items:
			del self._block_items[key]

			if self.block_rendering and _ANSI_ENABLED:
				self._render_block(prepend_msg)
			else:
				self._block_reserved_lines = len(self._get_all_block_lines())
				self.block_rendering = self._block_reserved_lines > 0
	
	def prepend_message(self, msg: str):
		"""Print a message above the current progress block."""
		if not _ANSI_ENABLED and not self.block_rendering:
			# Fallback: simple print
			print(msg)
			return
		
		self._render_block(prepend_msg=msg)
	
	def _get_all_block_lines(self) -> list[str]:
		"""Get all current block lines (header + items)."""
		if self._block_header:
			lines = [self.HEADER_SEPARATOR, *self._block_header.values(), self.HEADER_SEPARATOR, ""]
		else:
			lines = []
		
		lines.extend(self._block_items.values())
		
		return ["", *lines] if lines else [] # Add blank space at the beginning if populated

	def _render_block(self, prepend_msg: str = ""):
		"""
		Re-render the progress block (lock held).
		If msg provided, print it first then re-render block below.
		"""
		def _move_cursor_up(lines: int) -> str:
			"""ANSI escape sequence to move cursor up N lines."""
			return f"\x1b[{lines}A"

		def _overwrite_line_at_cursor(msg: str) -> str:
			"""ANSI escape sequence to overwrite current line + string + move down to next line."""
			return f"\x1b[2K\r{msg}\n"
		
		prev_count = self._block_reserved_lines

		lines = self._get_all_block_lines()
		new_count = len(lines)
		total_lines_written = new_count
		output = ""
	
		# Move cursor to start of the last-printed block
		if prev_count > 0:
			output = _move_cursor_up(prev_count)
		
		# If message provided, handle clearing and message printing
		if prepend_msg:
			# Print message on first line
			output += _overwrite_line_at_cursor(prepend_msg)
			total_lines_written += 1
		
		# Render all block lines
		for line in lines:
			output += _overwrite_line_at_cursor(line)
		
		# Clear leftover lines if block shrunk
		if prev_count > total_lines_written:
			extra = prev_count - total_lines_written
			for _ in range(extra):
				output += _overwrite_line_at_cursor("")

			output += _move_cursor_up(extra)
		
		# Single atomic write
		sys.stdout.write(output)
		sys.stdout.flush()

		self._block_reserved_lines = new_count
		self.block_rendering = new_count > 0

	def clear_all(self):
		"""Clear any stored block items and headers"""
		self._block_header.clear()
		self._block_items.clear()
		self._last_prints.clear()

		self._render_block()

# Global singleton instance
_block_renderer: Optional[BlockRenderer] = None

def get_block_renderer() -> BlockRenderer:
	"""Get or create the global console renderer singleton."""
	global _block_renderer
	
	if _block_renderer is None:
		_block_renderer = BlockRenderer()

	return _block_renderer
