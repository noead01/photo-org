from enum import StrEnum

class FilesizeRange(StrEnum):
    small  = "small"
    medium = "medium"
    large  = "large"

    def bounds(self) -> tuple[int, int]:
        return {
            FilesizeRange.small:  (0, 1_000_000),
            FilesizeRange.medium: (1_000_000, 5_000_000),
            FilesizeRange.large:  (5_000_000, 10_000_000_000),
        }[self]
