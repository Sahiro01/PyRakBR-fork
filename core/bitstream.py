
from __future__ import annotations

import struct


_HUFFMAN_FREQUENCIES = (
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 722, 0, 0, 2, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    11084, 58, 63, 1, 0, 31, 0, 317, 64, 64, 44, 0, 695, 62, 980, 266,
    69, 67, 56, 7, 73, 3, 14, 2, 69, 1, 167, 9, 1, 2, 25, 94,
    0, 195, 139, 34, 96, 48, 103, 56, 125, 653, 21, 5, 23, 64, 85, 44,
    34, 7, 92, 76, 147, 12, 14, 57, 15, 39, 15, 1, 1, 1, 2, 3, 0,
    3611, 845, 1077, 1884, 5870, 841, 1057, 2501, 3212, 164, 531, 2019, 1330, 3056, 4037, 848,
    47, 2586, 2919, 4771, 1707, 535, 1106, 152, 1243, 100, 0, 2, 0, 10, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0,
)


class _HuffmanNode:
    __slots__ = ("value", "left", "right")

    def __init__(self, value: int = -1):
        self.value = value
        self.left: _HuffmanNode | None = None
        self.right: _HuffmanNode | None = None

    @property
    def is_leaf(self) -> bool:
        return self.left is None and self.right is None


def _insert_sorted(node_list: list, weight: int, tiebreak: int, node: _HuffmanNode) -> None:
    for idx in range(len(node_list)):
        if node_list[idx][0] >= weight:
            node_list.insert(idx, [weight, tiebreak, node])
            return
    node_list.append([weight, tiebreak, node])


def _build_huffman_tree(frequencies: tuple[int, ...]) -> _HuffmanNode:
    nodes = []
    for i in range(256):
        freq = frequencies[i] if frequencies[i] != 0 else 1
        _insert_sorted(nodes, freq, i, _HuffmanNode(i))

    while len(nodes) > 1:
        f1, _, left = nodes.pop(0)
        f2, _, right = nodes.pop(0)
        parent = _HuffmanNode()
        parent.left = left
        parent.right = right
        _insert_sorted(nodes, f1 + f2, left.value, parent)

    return nodes[0][2]


_HUFFMAN_TREE = _build_huffman_tree(_HUFFMAN_FREQUENCIES)


class BitStream:

    __slots__ = ("_buffer", "bitpos", "skipped_bits")

    def __init__(self, data: bytes | bytearray | None = None):
        self._buffer = bytearray(data or b"")
        self.bitpos = 0
        self.skipped_bits = 0

    def _ensure_capacity(self, bits: int) -> None:
        total_bits = self.bitpos + bits
        required_bytes = (total_bits + 7) // 8

        if len(self._buffer) < required_bytes:
            self._buffer.extend(b"\x00" * (required_bytes - len(self._buffer)))

    def _read_struct(self, fmt: str, size: int):
        pos = self.bitpos

        if pos % 8:
            return struct.unpack(fmt, self.read_bytes(size))[0]

        start = pos // 8
        end = start + size

        if end > len(self._buffer):
            raise EOFError("Not enough bytes")

        value = struct.unpack_from(fmt, self._buffer, start)[0]
        self.bitpos = pos + size * 8
        return value

    def write_bit(self, bit: int) -> None:
        self._ensure_capacity(1)

        byte_index = self.bitpos // 8
        bit_index = 7 - (self.bitpos % 8)
        mask = 1 << bit_index

        if bit:
            self._buffer[byte_index] |= mask
        else:
            self._buffer[byte_index] &= ~mask

        self.bitpos += 1

    def write_bits(self, value: int, count: int) -> None:
        if count < 0:
            raise ValueError("count must be >= 0")

        if count == 0:
            return

        pos = self.bitpos
        buf = self._buffer
        is_append = (pos == len(buf) * 8)

        if count % 8 == 0 and pos % 8 == 0:
            nbytes = count // 8
            masked = (value & ((1 << count) - 1)).to_bytes(nbytes, "big")

            if is_append:
                buf.extend(masked)
            else:
                start = pos // 8
                self._ensure_capacity(count)
                self._buffer[start:start + nbytes] = masked

            self.bitpos = pos + count
            return

        self._ensure_capacity(count)
        buf = self._buffer

        for i in reversed(range(count)):
            byte_index = pos // 8
            bit_index = 7 - (pos % 8)
            mask = 1 << bit_index

            if (value >> i) & 1:
                buf[byte_index] |= mask
            else:
                buf[byte_index] &= ~mask

            pos += 1

        self.bitpos = pos

    def write_uint8(self, value: int) -> None:
        self.write_bytes(struct.pack("<B", value & 0xFF))

    def write_uint16(self, value: int) -> None:
        self.write_bytes(struct.pack("<H", value & 0xFFFF))

    def write_uint32(self, value: int) -> None:
        self.write_bytes(struct.pack("<I", value & 0xFFFFFFFF))

    def write_int8(self, value: int) -> None:
        self.write_bytes(struct.pack("<b", int(value)))

    def write_int16(self, value: int) -> None:
        self.write_bytes(struct.pack("<h", int(value)))

    def write_int32(self, value: int) -> None:
        self.write_bytes(struct.pack("<i", int(value)))

    def write_float(self, value: float) -> None:
        self.write_bytes(struct.pack("<f", float(value)))

    def write_bool(self, value: bool) -> None:
        self.write_bit(1 if value else 0)

    def write_bytes(self, data: bytes) -> None:
        if not data:
            return

        if self.bitpos % 8 == 0:
            buf = self._buffer
            start = self.bitpos // 8

            if start == len(buf):
                buf.extend(data)
            else:
                end = start + len(data)
                if end > len(buf):
                    buf.extend(b"\x00" * (end - len(buf)))
                buf[start:end] = data

            self.bitpos += len(data) * 8
            return

        for b in data:
            self.write_bits(b, 8)

    def write_compressed(self, value: int, size: int, unsigned: bool = True) -> None:

        num_bytes = size >> 3
        byte_match = 0x00 if unsigned else 0xFF
        half_byte_match = 0x00 if unsigned else 0xF0

        raw = value.to_bytes(num_bytes, byteorder="little", signed=(not unsigned))

        
        current_byte = num_bytes - 1

        while current_byte > 0:
            if raw[current_byte] == byte_match:
                self.write_bool(True)
            else:
                self.write_bool(False)
                for i in range(current_byte + 1):
                    self.write_bits(raw[i], 8)
                return
            current_byte -= 1

        low_byte = raw[0]
        upper_nibble = low_byte & 0xF0

        if upper_nibble == half_byte_match:
            self.write_bool(True)
            self.write_bits(low_byte & 0x0F, 4)
        else:
            self.write_bool(False)
            self.write_bits(low_byte, 8)

    def read_bit(self) -> int:
        if self.bitpos >= len(self._buffer) * 8:
            raise EOFError("No more bits")

        byte_index = self.bitpos // 8
        bit_index = 7 - (self.bitpos % 8)

        value = (self._buffer[byte_index] >> bit_index) & 1

        self.bitpos += 1
        return value

    def read_bits(self, count: int) -> int:
        if count < 0:
            raise ValueError("count must be >= 0")

        if count == 0:
            return 0

        pos = self.bitpos
        buf = self._buffer

        if count % 8 == 0 and pos % 8 == 0:
            nbytes = count // 8
            start = pos // 8
            end = start + nbytes

            if end > len(buf):
                raise EOFError("No more bits")

            self.bitpos = pos + count
            return int.from_bytes(buf[start:end], "big")

        if pos + count > len(buf) * 8:
            raise EOFError("No more bits")

        value = 0
        remaining = count

        while remaining > 0:
            byte_index = pos // 8
            bit_in_byte = pos % 8
            bits_available_in_byte = 8 - bit_in_byte
            take = bits_available_in_byte if bits_available_in_byte < remaining else remaining

            byte_val = buf[byte_index]
            shift = bits_available_in_byte - take
            chunk = (byte_val >> shift) & ((1 << take) - 1)

            value = (value << take) | chunk
            pos += take
            remaining -= take

        self.bitpos = pos
        return value

    def read_uint8(self) -> int:
        pos = self.bitpos

        if pos % 8:
            return self.read_bits(8)

        index = pos // 8

        if index >= len(self._buffer):
            raise EOFError("No more bits")

        self.bitpos = pos + 8
        return self._buffer[index]

    def read_bool(self) -> bool:
        return bool(self.read_bit())

    def read_bytes(self, count: int) -> bytes:
        if count <= 0:
            return b""

        if self.bitpos % 8 == 0:
            start = self.bitpos // 8
            end = start + count

            if end > len(self._buffer):
                raise EOFError("Not enough bytes")

            self.bitpos += count * 8
            return bytes(self._buffer[start:end])

        return self.read_bits(count * 8).to_bytes(count, "big")

    @staticmethod
    def _decode_string(
        data: bytes | bytearray,
        encoding: str,
        errors: str
    ) -> str:
        text = bytes(data).decode(encoding, errors=errors)

        return (
            text
            .replace("\\r\\n", "\n")
            .replace("\\n", "\n")
            .replace("\r\n", "\n")
            .replace("\r", "\n")
        )

    def read_string(
        self,
        length: int,
        encoding: str = "utf-8",
        errors: str = "strict"
    ) -> str:
        return self._decode_string(
            self.read_bytes(length),
            encoding,
            errors
        )

    def read_cstring(
        self,
        encoding: str = "utf-8",
        errors: str = "strict",
        max_length: int | None = None
    ) -> str:
        if max_length is not None and max_length < 0:
            raise ValueError("max_length must be >= 0")

        available = self.remaining_bits // 8
        length = (
            available
            if max_length is None
            else min(available, max_length)
        )

        if self.bitpos % 8 == 0:
            start = self.bitpos // 8
            end = start + length
            terminator = self._buffer.find(b"\x00", start, end)

            if terminator < 0:
                terminator = end
                self.bitpos += length * 8
            else:
                self.bitpos = (terminator + 1) * 8

            return self._decode_string(
                self._buffer[start:terminator],
                encoding,
                errors
            )

        raw = bytearray()

        for _ in range(length):
            value = self.read_uint8()

            if value == 0:
                break

            raw.append(value)

        return self._decode_string(
            raw,
            encoding,
            errors
        )

    def read_float(self) -> float:
        return self._read_struct("<f", 4)

    def read_uint16(self) -> int:
        return self._read_struct("<H", 2)

    def read_uint32(self) -> int:
        return self._read_struct("<I", 4)

    def read_int8(self) -> int:
        value = self.read_uint8()
        return value - 0x100 if value & 0x80 else value

    def read_int16(self) -> int:
        return self._read_struct("<h", 2)

    def read_int32(self) -> int:
        return self._read_struct("<i", 4)

    def read_compressed(self, size: int, unsigned: bool = True) -> int:

        num_bytes = size >> 3
        byte_match = 0x00 if unsigned else 0xFF
        half_byte_match = 0xF0 if not unsigned else 0x00

        output = bytearray(num_bytes)

        current_byte = num_bytes - 1

        while current_byte > 0:
            flag = self.read_bool()

            if flag:
                output[current_byte] = byte_match
                current_byte -= 1
            else:
                for i in range(current_byte + 1):
                    output[i] = self.read_bits(8)

                return int.from_bytes(
                    output, byteorder="little", signed=(not unsigned)
                )

        flag = self.read_bool()

        if flag:
            low_nibble = self.read_bits(4)
            output[0] = half_byte_match | low_nibble
        else:
            output[0] = self.read_bits(8)

        return int.from_bytes(output, byteorder="little", signed=(not unsigned))

    def read_compressed_string(
        self,
        max_chars: int = 256,
        encoding: str = "utf-8",
        errors: str = "strict"
    ) -> str:
        string_bit_length = self.read_compressed(16, unsigned=True)

        if string_bit_length == 0:
            return ""

        if self.remaining_bits < string_bit_length:
            raise EOFError("Not enough bits for compressed string")

        node = _HUFFMAN_TREE
        chars_written = 0
        result = bytearray()

        for _ in range(string_bit_length):
            bit = self.read_bit()

            if bit == 0:
                node = node.left
            else:
                node = node.right

            if node.is_leaf:
                if chars_written < max_chars:
                    result.append(node.value)
                    chars_written += 1
                node = _HUFFMAN_TREE

        return self._decode_string(result, encoding, errors)

    def align_to_byte(self) -> None:
        mod = self.bitpos % 8

        if mod:
            self.bitpos += 8 - mod

    def seek_bits(self, pos: int) -> None:
        if pos < 0:
            raise ValueError("negative seek")

        self.bitpos = pos

    def skip_bits(self, count: int) -> None:
        self.skipped_bits += count
        self.seek_bits(self.bitpos + count)

    @property
    def remaining_bits(self) -> int:
        return len(self._buffer) * 8 - self.bitpos

    def get_bytes(self) -> bytes:
        used = (self.bitpos + 7) // 8
        return bytes(self._buffer[:used])

    def __len__(self) -> int:
        return self.bitpos

    def __repr__(self) -> str:
        return (
            f"BitStream(bits={self.bitpos}, "
            f"bytes={len(self._buffer)}, "
            f"skipped={self.skipped_bits})"
        )
