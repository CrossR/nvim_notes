
from typing import List

class mock_nvim:

    def __init__(self) -> None:
        self.api: mock_nvim_api = mock_nvim_api(self)
        self.current: mock_current = mock_current()

class mock_nvim_api:
    def __init__(self, nvim_mock: mock_nvim) -> None:
        self.nvim: mock_nvim = mock_nvim

    def buf_set_lines(
        self,
        buffer: int,
        start: int,
        end: int,
        strict_indexing: bool,
        replacement: List[str],
    ) -> None:

        self.nvim.current.buffer.lines[start:end] = replacement

    def buf_get_lines(
        self,
        buffer: int,
        start: int,
        end: int,
        strict_indexing: bool,
    ) -> List[str]:

        return self.nvim.current.buffer.lines[start:end]

class mock_current:

    def __init__(self) -> None:
        self.window: mock_window = mock_window()
        self.buffer: mock_buffer = mock_buffer()

class mock_buffer:

    def __init__(self) -> None:
        self.number: int = 0
        self.lines: List[str] = [""]

class mock_window:

    def __init__(self) -> None:
        self.cursor: tuple = tuple()
