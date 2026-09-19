import time
import threading
from collections import deque

from .bitstream import BitStream
from . import security
from core import logger
from samp.constants import PacketReliability, PacketPriority


_ORDERING_METADATA_RELIABILITIES = frozenset({
    PacketReliability.UNRELIABLE_SEQUENCED,
    PacketReliability.RELIABLE_ORDERED,
    PacketReliability.RELIABLE_SEQUENCED,
})

_SEQUENCED_RELIABILITIES = frozenset({
    PacketReliability.UNRELIABLE_SEQUENCED,
    PacketReliability.RELIABLE_SEQUENCED,
})

_RELIABLE_RELIABILITIES = frozenset({
    PacketReliability.RELIABLE,
    PacketReliability.RELIABLE_ORDERED,
    PacketReliability.RELIABLE_SEQUENCED,
})

_PING_MULTIPLIER_TO_RESEND = 3.0
_DEFAULT_PING_MS = 100
_MIN_PING_MS = 30
_MAX_PING_MS = 500
_PING_EWMA_ALPHA = 0.125

_MAX_RAKNET_DATAGRAM_BYTES = 500  

_MAX_ACK_DATAGRAM_BYTES = _MAX_RAKNET_DATAGRAM_BYTES

_SPLIT_TIMEOUT_SEC = 30.0
_COMPLETED_SPLIT_CACHE_SIZE = 2048

_MAX_RECV_DATAGRAMS_PER_PUMP = 64
_MAX_RECV_PUMP_TIME_SEC = 0.003
_RECV_BUFFER_SOFT_LIMIT = 4096

_RECEIVED_RELIABLE_CACHE_SIZE = 8192
_DUPLICATE_MESSAGE_WARNING_THRESHOLD = 100
_ORDERING_CHANNEL_COUNT = 16
_ORDERING_INDEX_MASK = 0xFFFF
_ORDERING_INDEX_HALF_RANGE = 0x8000

_QueueEntry = tuple[bytes, bytes, int, bytes, int]


class RakNetProtocol:
    def __init__(self, network, security_layer=None):
        self.network = network
        self.security = security if security_layer is None else security_layer

        self.message_number = 0
        self.split_packet_id = 0

        self.pending_acks = {}
        self.resend_queue: dict[int, tuple] = {}

        self.ordering_indices = [0] * _ORDERING_CHANNEL_COUNT
        self._ordered_read_indices = [0] * _ORDERING_CHANNEL_COUNT
        self._sequenced_read_indices = [0] * _ORDERING_CHANNEL_COUNT
        self._ordered_packet_buffers: list[dict[int, dict]] = [
            {} for _ in range(_ORDERING_CHANNEL_COUNT)
        ]
        self._ordering_lock = threading.Lock()

        self._ack_pending: set[int] = set()
        self._ack_lock = threading.Lock()
        self._ack_flush_lock = threading.Lock()
        self._ping_ms: float = _DEFAULT_PING_MS
        self._has_ping_sample = False
        self._next_ack_time: float = time.monotonic()

        self._recv_buffer: deque[dict] = deque()

        self._received_reliable_order: deque[int] = deque()
        self._received_reliable_numbers: set[int] = set()
        self._received_reliable_duplicates: dict[int, int] = {}
        self._received_message_highest: int | None = None
        self._received_reliable_lock = threading.Lock()

        self._send_queues: list[deque[_QueueEntry]] = [
            deque()
            for _ in range(PacketPriority.NUMBER_OF_PRIORITIES)
        ]

        self._split_packets: dict[tuple, dict] = {}
        self._completed_split_packets: dict[tuple, float] = {}

        self.on_send_packet = None

    def _next_message_number(self) -> int:
        current = self.message_number
        self.message_number = (current + 1) & 0xFFFF
        return current

    def _next_split_packet_id(self) -> int:
        current = self.split_packet_id
        self.split_packet_id = (self.split_packet_id + 1) & 0xFFFF
        return current

    def _next_ordering_index(self, ordering_channel: int) -> int | None:
        if not 0 <= ordering_channel < len(self.ordering_indices):
            raise ValueError("ordering_channel must be in range 0..15")

        current = self.ordering_indices[ordering_channel]
        self.ordering_indices[ordering_channel] = (current + 1) & 0xFFFF
        return current

    @staticmethod
    def _has_ordering_metadata(reliability: int) -> bool:
        return reliability in _ORDERING_METADATA_RELIABILITIES

    @staticmethod
    def _is_reliable_reliability(reliability: int) -> bool:
        return reliability in _RELIABLE_RELIABILITIES

    @staticmethod
    def _is_encrypted_reliability(reliability: int) -> bool:
        
        return reliability in _RELIABLE_RELIABILITIES

    def _build_header(
        self,
        reliability: int,
        data_bitlength: int,
        ordering_channel: int = 0,
        is_first_packet: bool = True,
        has_ack: bool = False,
        has_split: bool = False,
        checksum_byte: int | None = None,
        encrypted_payload: bool = False,
        message_number: int | None = None,
        ordering_index: int | None = None,
        split_id: int | None = None,
        split_index: int | None = None,
        split_count: int | None = None,
    ) -> tuple[bytes, int, int | None]:

        if message_number is None:
            msg_num = self._next_message_number()
        else:
            msg_num = int(message_number) & 0xFFFF

        bs = BitStream()

        
        if is_first_packet:
            bs.write_bool(has_ack)

        bs.write_uint16(msg_num)

        
        bs.write_bits(int(reliability) & 0x07, 3)

        
        if encrypted_payload:
            if checksum_byte is None:
                checksum_byte = 0

            bs.write_bits(checksum_byte & 0xFF, 8)

        
        
        
        
        
        if self._has_ordering_metadata(reliability):
            ordering_channel &= 0x0F

            if ordering_index is None:
                ordering_index = self.ordering_indices[ordering_channel]
                self.ordering_indices[ordering_channel] = (
                    ordering_index + 1
                ) & 0xFFFF
            else:
                ordering_index = int(ordering_index) & 0xFFFF

            bs.write_uint16(ordering_index)
            bs.write_bits((~ordering_channel) & 0x0F, 4)

        
        
        bs.write_bool(has_split)

        if has_split:
            if split_id is None or split_index is None or split_count is None:
                raise ValueError(
                    "split_id, split_index and split_count are required "
                    "when has_split=True"
                )

            if split_count <= 0 or not 0 <= split_index < split_count:
                raise ValueError("invalid outgoing split packet indices")

            bs.write_uint16(split_id)
            bs.write_compressed(split_index, 32, unsigned=True)
            bs.write_compressed(split_count, 32, unsigned=True)

        bs.write_compressed(data_bitlength, 16, unsigned=True)
        bs.align_to_byte()

        return bs.get_bytes(), msg_num, ordering_index

    def _build_headers(self, **kwargs) -> tuple[bytes, bytes, int]:
        standalone, msg_num, order = self._build_header(**kwargs)
        kwargs.update(message_number=msg_num, ordering_index=order,
                      is_first_packet=False, has_ack=False)
        compact, _, _ = self._build_header(**kwargs)
        return standalone, compact, msg_num

    def _update_ping_from_rtt(self, sample_ms: float) -> None:
        if sample_ms <= 0.0:
            return

        sample_ms = max(_MIN_PING_MS, min(_MAX_PING_MS, sample_ms))

        with self._ack_lock:
            if not self._has_ping_sample:
                self._ping_ms = sample_ms
                self._has_ping_sample = True
            else:
                self._ping_ms += (
                    sample_ms - self._ping_ms
                ) * _PING_EWMA_ALPHA

    def _remove_pending(self, msg_num: int) -> None:
        sent_at = self.pending_acks.pop(msg_num, None)

        if sent_at is not None:
            self._update_ping_from_rtt(
                (time.monotonic() - sent_at) * 1000.0
            )

        self.resend_queue.pop(msg_num, None)

    @staticmethod
    def _build_ranges(ids: list[int]) -> list[tuple[int, int]]:
        if not ids:
            return []

        ranges: list[tuple[int, int]] = []

        start = end = ids[0]

        for n in ids[1:]:
            if n == end + 1:
                end = n
            else:
                ranges.append((start, end))
                start = end = n

        ranges.append((start, end))

        return ranges

    @staticmethod
    def _serialize_range_list(
        bs: BitStream,
        ranges: list[tuple[int, int]],
    ) -> None:
        bs.write_compressed(len(ranges), 16, unsigned=True)

        for rmin, rmax in ranges:
            bs.write_bool(rmin == rmax)

            bs.write_uint16(rmin)

            if rmin != rmax:
                bs.write_uint16(rmax)

    @staticmethod
    def _deserialize_range_list(bs: BitStream) -> list[tuple[int, int]]:
        count = bs.read_compressed(16, unsigned=True)

        ranges = []

        for _ in range(count):
            max_eq_min = bs.read_bool()

            rmin = bs.read_uint16()

            if max_eq_min:
                rmax = rmin
            else:
                rmax = bs.read_uint16()

            ranges.append((rmin, rmax))

        return ranges

    def _queue_ack(self, packet_id: int) -> None:
        with self._ack_lock:
            self._ack_pending.add(int(packet_id) & 0xFFFF)

    def _should_flush(self, now: float | None = None) -> bool:
        if now is None:
            now = time.monotonic()

        with self._ack_lock:
            return bool(self._ack_pending) and now >= self._next_ack_time

    @staticmethod
    def _compressed_uint16_bits(value: int) -> int:
        value &= 0xFFFF

        if value >= 0x100:
            return 17

        if value >= 0x10:
            return 10

        return 6

    @classmethod
    def _take_ranges_for_ack_datagram(
        cls,
        ranges: list[tuple[int, int]],
        max_bytes: int = _MAX_ACK_DATAGRAM_BYTES,
    ) -> list[tuple[int, int]]:
        selected: list[tuple[int, int]] = []
        range_bits = 0

        for rmin, rmax in ranges:
            candidate_count = len(selected) + 1
            candidate_range_bits = range_bits + (17 if rmin == rmax else 33)
            total_bits = (
                1
                + cls._compressed_uint16_bits(candidate_count)
                + candidate_range_bits
            )

            if selected and (total_bits + 7) // 8 > max_bytes:
                break

            selected.append((rmin, rmax))
            range_bits = candidate_range_bits

        return selected

    def _flush_acks(self) -> None:
        with self._ack_flush_lock:
            with self._ack_lock:
                if not self._ack_pending:
                    return

                ids = sorted(self._ack_pending)
                ranges = self._build_ranges(ids)
                selected_ranges = self._take_ranges_for_ack_datagram(ranges)
                last_selected_id = selected_ranges[-1][1]
                selected_ids = [n for n in ids if n <= last_selected_id]
                self._ack_pending.difference_update(selected_ids)

            bs = BitStream()
            bs.write_bool(True)
            self._serialize_range_list(bs, selected_ranges)
            bs.align_to_byte()

            try:
                ack_data = bs.get_bytes()
                self.network.send(ack_data)
            except Exception:
                with self._ack_lock:
                    self._ack_pending.update(selected_ids)
                    self._next_ack_time = time.monotonic()
                raise

            now = time.monotonic()
            delay = (
                max(_MIN_PING_MS, self._ping_ms)
                * (_PING_MULTIPLIER_TO_RESEND / 4.0)
                / 1000.0
            )

            with self._ack_lock:
                if self._ack_pending:
                    self._next_ack_time = now
                else:
                    self._next_ack_time = now + delay

    def reset_ack_state(self) -> None:
        with self._ack_flush_lock:
            with self._ack_lock:
                self._ack_pending.clear()
                self._ping_ms = _DEFAULT_PING_MS
                self._has_ping_sample = False
                self._next_ack_time = time.monotonic()

        with self._received_reliable_lock:
            self._received_reliable_order.clear()
            self._received_reliable_numbers.clear()
            self._received_reliable_duplicates.clear()
            self._received_message_highest = None

        with self._ordering_lock:
            self._ordered_read_indices = [0] * _ORDERING_CHANNEL_COUNT
            self._sequenced_read_indices = [0] * _ORDERING_CHANNEL_COUNT
            for buffer in self._ordered_packet_buffers:
                buffer.clear()

        self._completed_split_packets.clear()

    def _extend_received_message_number(self, pkt: dict) -> int | None:
        message_number = pkt.get("message_number")
        if message_number is None:
            return None

        raw = int(message_number) & 0xFFFF
        with self._received_reliable_lock:
            highest = self._received_message_highest
            if highest is None:
                extended = raw
                self._received_message_highest = extended
            else:
                extended = (highest & ~0xFFFF) | raw
                if extended - highest > 0x8000:
                    extended -= 0x10000
                elif highest - extended > 0x8000:
                    extended += 0x10000

                if extended > highest:
                    self._received_message_highest = extended

        pkt["extended_message_number"] = extended
        return extended

    def _is_duplicate_reliable_packet(self, pkt: dict) -> bool:
        reliability = pkt.get("reliability")
        if not self._is_reliable_reliability(reliability):
            return False

        raw_message_number = pkt.get("message_number")
        if raw_message_number is None:
            return False
        raw_message_number = int(raw_message_number) & 0xFFFF
        message_number = pkt.get("extended_message_number")
        if message_number is None:
            message_number = self._extend_received_message_number(pkt)
        if message_number is None:
            return False
        message_number = int(message_number)

        warning_repeats = None

        with self._received_reliable_lock:
            if message_number in self._received_reliable_numbers:
                repeats = (
                    self._received_reliable_duplicates.get(message_number, 0)
                    + 1
                )
                self._received_reliable_duplicates[message_number] = repeats
                if repeats == _DUPLICATE_MESSAGE_WARNING_THRESHOLD + 1:
                    warning_repeats = repeats
                duplicate = True
            else:
                while (
                    len(self._received_reliable_order)
                    >= _RECEIVED_RELIABLE_CACHE_SIZE
                ):
                    expired = self._received_reliable_order.popleft()
                    self._received_reliable_numbers.discard(expired)
                    self._received_reliable_duplicates.pop(expired, None)

                self._received_reliable_order.append(message_number)
                self._received_reliable_numbers.add(message_number)
                self._received_reliable_duplicates[message_number] = 0
                duplicate = False

        if warning_repeats is not None:
            logger.warn(
                "RakNet reliable packet was resent more than "
                f"{_DUPLICATE_MESSAGE_WARNING_THRESHOLD} times | "
                f"message_number={raw_message_number}, "
                f"extended_message_number={message_number}, "
                f"repeats={warning_repeats}. "
                "The server may not be receiving our ACKs."
            )

        return duplicate

    @staticmethod
    def _ordering_index_delta(index: int, expected: int) -> int:
        return (index - expected) & _ORDERING_INDEX_MASK

    def _deliver_ordered_packet(self, pkt: dict) -> list[dict]:
        channel = pkt.get("ordering_channel")
        index = pkt.get("ordering_index")

        if channel is None or index is None:
            return []

        channel = int(channel)
        if not 0 <= channel < _ORDERING_CHANNEL_COUNT:
            return []

        index = int(index) & _ORDERING_INDEX_MASK

        with self._ordering_lock:
            expected = self._ordered_read_indices[channel]
            delta = self._ordering_index_delta(index, expected)

            if delta == 0:
                delivered = [pkt]
                expected = (expected + 1) & _ORDERING_INDEX_MASK
                buffer = self._ordered_packet_buffers[channel]

                while expected in buffer:
                    delivered.append(buffer.pop(expected))
                    expected = (expected + 1) & _ORDERING_INDEX_MASK

                self._ordered_read_indices[channel] = expected
                return delivered

            if delta < _ORDERING_INDEX_HALF_RANGE:
                self._ordered_packet_buffers[channel].setdefault(index, pkt)

        return []

    def _deliver_sequenced_packet(self, pkt: dict) -> list[dict]:
        channel = pkt.get("ordering_channel")
        index = pkt.get("ordering_index")

        if channel is None or index is None:
            return []

        channel = int(channel)
        if not 0 <= channel < _ORDERING_CHANNEL_COUNT:
            return []

        index = int(index) & _ORDERING_INDEX_MASK

        with self._ordering_lock:
            expected = self._sequenced_read_indices[channel]
            delta = self._ordering_index_delta(index, expected)

            if delta >= _ORDERING_INDEX_HALF_RANGE:
                return []

            self._sequenced_read_indices[channel] = (
                index + 1
            ) & _ORDERING_INDEX_MASK

        return [pkt]

    def _apply_delivery_order(self, pkt: dict) -> list[dict]:
        reliability = pkt.get("reliability")

        if reliability == PacketReliability.RELIABLE_ORDERED:
            return self._deliver_ordered_packet(pkt)

        if reliability in _SEQUENCED_RELIABILITIES:
            return self._deliver_sequenced_packet(pkt)

        return [pkt]

    @staticmethod
    def _split_group_key(pkt: dict) -> tuple:
        split_index = int(pkt.get("split_index") or 0)
        extended = pkt.get("extended_message_number")
        if extended is None:
            extended = int(pkt.get("message_number") or 0) & 0xFFFF
        first_fragment_number = int(extended) - split_index
        return (
            int(pkt.get("split_id") or 0) & 0xFFFF,
            int(pkt.get("split_count") or 0),
            first_fragment_number,
            pkt.get("ordering_channel"),
            pkt.get("ordering_index"),
            pkt.get("reliability"),
        )

    def _cleanup_old_split_packets(self, now: float | None = None) -> None:
        if now is None:
            now = time.monotonic()

        expired = [
            split_id
            for split_id, entry in self._split_packets.items()
            if now - entry.get("created_at", now) > _SPLIT_TIMEOUT_SEC
        ]

        for split_id in expired:
            del self._split_packets[split_id]

    def _cleanup_completed_split_packets(self) -> None:
        while len(self._completed_split_packets) > _COMPLETED_SPLIT_CACHE_SIZE:
            first_key = next(iter(self._completed_split_packets))
            self._completed_split_packets.pop(first_key, None)

    def _handle_split_packet(self, pkt: dict) -> dict | None:

        split_id = pkt.get("split_id")
        split_index = pkt.get("split_index")
        split_count = pkt.get("split_count")

        if split_id is None or split_index is None or split_count is None:
            return None

        if split_count <= 0:
            return None

        if split_index >= split_count:
            return None

        now = time.monotonic()
        self._cleanup_old_split_packets(now)
        self._cleanup_completed_split_packets()

        group_key = self._split_group_key(pkt)
        if group_key in self._completed_split_packets:
            return None

        entry = self._split_packets.get(group_key)

        if entry is not None and entry.get("count") != split_count:
            del self._split_packets[group_key]
            entry = None

        if entry is None:
            entry = {
                "count": split_count,
                "parts": {},
                "first": pkt,
                "created_at": time.monotonic(),
            }

            self._split_packets[group_key] = entry

        parts: dict[int, bytes] = entry["parts"]

        parts[split_index] = pkt["data"]

        if len(parts) < split_count:
            return None

        missing = [
            i
            for i in range(split_count)
            if i not in parts
        ]

        if missing:
            return None

        full_data = b"".join(
            parts[i]
            for i in range(split_count)
        )

        del self._split_packets[group_key]
        self._completed_split_packets[group_key] = now
        self._cleanup_completed_split_packets()

        full_pkt = dict(entry["first"])

        full_pkt["has_split"] = False
        full_pkt["split_id"] = split_id
        full_pkt["split_index"] = None
        full_pkt["split_count"] = split_count
        full_pkt["bitlen"] = len(full_data) * 8
        full_pkt["data"] = full_data
        full_pkt["encrypted_data"] = None
        full_pkt["reassembled"] = True

        return full_pkt

    def _notify_packet_sent(self, data: bytes, meta: dict | None = None) -> None:
        callback = self.on_send_packet

        if callback is None:
            return

        if meta is None:
            meta = {}

        try:
            callback(data, meta)
        except Exception as e:
            logger.error(f"on_send_packet callback error: {e}")

    def _make_queue_entry(
        self,
        data: bytes,
        reliability: int,
        ordering_channel: int,
        should_encrypt: bool,
        message_number: int,
        ordering_index: int | None,
        *,
        has_ack: bool = False,
        split_id: int | None = None,
        split_index: int | None = None,
        split_count: int | None = None,
        encoded_body: tuple[bytes, int | None] | None = None,
    ) -> _QueueEntry:
        
        if encoded_body is not None:
            body, checksum_byte = encoded_body
        elif should_encrypt:
            body, checksum_byte = self.security.encode_with_checksum(data)
        else:
            body = data
            checksum_byte = None

        is_split = split_id is not None
        header_kwargs = {
            "reliability": reliability,
            "data_bitlength": len(body) * 8,
            "ordering_channel": ordering_channel,
            "has_split": is_split,
            "checksum_byte": checksum_byte,
            "encrypted_payload": should_encrypt,
            "message_number": message_number,
            "ordering_index": ordering_index,
            "split_id": split_id,
            "split_index": split_index,
            "split_count": split_count,
        }

        standalone_header, msg_num, _ = self._build_header(
            is_first_packet=True,
            has_ack=has_ack,
            **header_kwargs,
        )
        compact_header, _, _ = self._build_header(
            is_first_packet=False,
            has_ack=False,
            **header_kwargs,
        )

        return (
            compact_header + body,
            standalone_header + body,
            msg_num,
            data,
            reliability,
        )

    def _find_split_chunk_size(
        self,
        data: bytes,
        reliability: int,
        ordering_channel: int,
        should_encrypt: bool,
        ordering_index: int | None,
        split_id: int,
    ) -> int:
        
        
        
        chunk_size = min(len(data) - 1, _MAX_RAKNET_DATAGRAM_BYTES)

        while chunk_size > 0:
            split_count = (len(data) + chunk_size - 1) // chunk_size
            preview = self._make_queue_entry(
                data[:chunk_size],
                reliability,
                ordering_channel,
                should_encrypt,
                message_number=0,
                ordering_index=ordering_index,
                split_id=split_id,
                
                split_index=split_count - 1,
                split_count=split_count,
            )
            preview_size = len(preview[1])

            if preview_size <= _MAX_RAKNET_DATAGRAM_BYTES:
                return chunk_size

            chunk_size -= max(
                1,
                preview_size - _MAX_RAKNET_DATAGRAM_BYTES,
            )

        raise ValueError("RakNet split header leaves no room for payload")

    def _make_outgoing_entries(
        self,
        data: bytes,
        reliability: int,
        ordering_channel: int,
        should_encrypt: bool,
        has_ack: bool,
        force_split: bool,
    ) -> list[_QueueEntry]:
        ordering_channel &= 0x0F
        ordering_index = (
            self.ordering_indices[ordering_channel]
            if self._has_ordering_metadata(reliability)
            else None
        )

        
        if should_encrypt:
            preview_body = self.security.encode_with_checksum(data)
        else:
            preview_body = (data, None)

        
        preview = self._make_queue_entry(
            data,
            reliability,
            ordering_channel,
            should_encrypt,
            message_number=self.message_number,
            ordering_index=ordering_index,
            has_ack=has_ack,
            encoded_body=preview_body,
        )

        needs_split = force_split or (
            len(preview[1]) > _MAX_RAKNET_DATAGRAM_BYTES
        )

        if not needs_split:
            msg_num = self._next_message_number()
            if msg_num != preview[2]:
                raise AssertionError("message number changed during preview")

            if self._has_ordering_metadata(reliability):
                used_ordering_index = self._next_ordering_index(
                    ordering_channel
                )
                if used_ordering_index != ordering_index:
                    raise AssertionError(
                        "ordering index changed during preview"
                    )

            return [preview]

        if len(data) < 2:
            raise ValueError(
                "Cannot split payload smaller than two bytes; its header "
                "already exceeds the configured datagram limit"
            )

        split_id = self._next_split_packet_id()
        chunk_size = self._find_split_chunk_size(
            data,
            reliability,
            ordering_channel,
            should_encrypt,
            ordering_index,
            split_id,
        )

        
        if force_split and chunk_size >= len(data):
            chunk_size = (len(data) + 1) // 2

        split_count = (len(data) + chunk_size - 1) // chunk_size

        if self._has_ordering_metadata(reliability):
            ordering_index = self._next_ordering_index(ordering_channel)

        entries: list[_QueueEntry] = []

        for split_index in range(split_count):
            start = split_index * chunk_size
            chunk = data[start:start + chunk_size]
            entry = self._make_queue_entry(
                chunk,
                reliability,
                ordering_channel,
                should_encrypt,
                message_number=self._next_message_number(),
                ordering_index=ordering_index,
                has_ack=has_ack and split_index == 0,
                split_id=split_id,
                split_index=split_index,
                split_count=split_count,
            )

            if len(entry[1]) > _MAX_RAKNET_DATAGRAM_BYTES:
                raise AssertionError(
                    "outgoing RakNet split fragment exceeds datagram limit"
                )

            entries.append(entry)

        return entries

    def _dispatch_datagram(
        self,
        entries: list[_QueueEntry],
        priority: int,
        entry_priorities: list[int] | None = None,
    ) -> None:

        if not entries:
            return

        if self._should_flush():
            self._flush_acks()

        now = time.monotonic()

        wire_packets = [
            standalone_packet if index == 0 else compact_packet
            for index, (
                compact_packet,
                standalone_packet,
                _msg_num,
                _original_data,
                _reliability,
            ) in enumerate(entries)
        ]
        datagram = b"".join(wire_packets)

        if len(datagram) > _MAX_RAKNET_DATAGRAM_BYTES:
            raise ValueError(
                f"connected RakNet datagram is {len(datagram)} bytes; "
                f"limit is {_MAX_RAKNET_DATAGRAM_BYTES}"
            )

        if entry_priorities is None:
            entry_priorities = [priority] * len(entries)
        elif len(entry_priorities) != len(entries):
            raise ValueError("entry priority count does not match entries")

        encrypted_datagram = datagram

        self.network.send(encrypted_datagram)

        self._notify_packet_sent(
            encrypted_datagram,
            {
                "kind": "datagram",
                "priority": priority,
                "is_resend": False,
                "size": len(encrypted_datagram),
                "entries": [
                    {
                        "message_number": msg_num,
                        "reliability": reliability,
                        "priority": entry_priority,
                        "full_packet": full_packet,
                        "original_payload": original_data,
                    }
                    for full_packet, entry_priority, (
                        _compact_packet,
                        _standalone_packet,
                        msg_num,
                        original_data,
                        reliability,
                    ) in zip(wire_packets, entry_priorities, entries)
                ],
            }
        )

        for (
            _compact_packet,
            standalone_packet,
            msg_num,
            original_data,
            reliability,
        ) in entries:

            if self._is_reliable_reliability(reliability):

                self.pending_acks[msg_num] = now

                self.resend_queue[msg_num] = (
                    msg_num,
                    original_data,
                    reliability,
                    standalone_packet,
                )

    def send_with_header(
        self,
        data: bytes,
        reliability: int,
        ordering_channel: int = 0,
        priority: int = PacketPriority.HIGH_PRIORITY,
        has_ack: bool = False,
        has_split: bool = False,
        encrypt: bool | None = None,
    ) -> None:
        
        
        if encrypt is None:
            should_encrypt = self._is_encrypted_reliability(reliability)
        else:
            should_encrypt = bool(encrypt)

        entries = self._make_outgoing_entries(
            bytes(data),
            reliability,
            ordering_channel,
            should_encrypt,
            has_ack,
            force_split=has_split,
        )

        if priority == PacketPriority.SYSTEM_PRIORITY:
            
            
            for entry in entries:
                self._dispatch_datagram([entry], priority)

        else:
            self._send_queues[priority].extend(entries)

    def send_raw(self, data: bytes) -> None:
        encrypted = data
        self.network.send(encrypted)

        self._notify_packet_sent(
            encrypted,
            {
                "kind": "raw",
                "priority": PacketPriority.SYSTEM_PRIORITY,
                "is_resend": False,
                "size": len(encrypted),
                "entries": [
                    {
                        "message_number": None,
                        "reliability": PacketReliability.UNRELIABLE,
                        "priority": PacketPriority.SYSTEM_PRIORITY,
                        "full_packet": data,
                        "original_payload": data,
                    }
                ],
            }
        )

    def update(self) -> None:

        if self._should_flush():
            self._flush_acks()

        send_priorities = (
            PacketPriority.HIGH_PRIORITY,
            PacketPriority.MEDIUM_PRIORITY,
            PacketPriority.LOW_PRIORITY,
        )

        while any(self._send_queues[p] for p in send_priorities):
            batch: list[_QueueEntry] = []
            batch_priorities: list[int] = []
            datagram_size = 0

            for priority in send_priorities:
                queue = self._send_queues[priority]

                while queue:
                    candidate = queue[0]
                    candidate_packet = (
                        candidate[1] if not batch else candidate[0]
                    )
                    candidate_size = len(candidate_packet)

                    if (
                        datagram_size + candidate_size
                        > _MAX_RAKNET_DATAGRAM_BYTES
                    ):
                        break

                    batch.append(queue.popleft())
                    batch_priorities.append(priority)
                    datagram_size += candidate_size

            if not batch:
                first_priority = next(
                    p for p in send_priorities if self._send_queues[p]
                )
                oversized_size = len(
                    self._send_queues[first_priority][0][1]
                )
                raise ValueError(
                    f"queued RakNet InternalPacket is {oversized_size} "
                    f"bytes; datagram limit is "
                    f"{_MAX_RAKNET_DATAGRAM_BYTES}"
                )

            self._dispatch_datagram(
                batch,
                batch_priorities[0],
                entry_priorities=batch_priorities,
            )

        now = time.monotonic()

        port = getattr(self.network, "port", 0)

        for (
            msg_num,
            data,
            reliability,
            full_packet,
        ) in list(self.resend_queue.values()):

            if (
                now
                - self.pending_acks.get(msg_num, 0)
            ) > 2.0:

                encrypted_packet = full_packet
                self.network.send(encrypted_packet)

                self._notify_packet_sent(
                    encrypted_packet,
                    {
                        "kind": "resend",
                        "priority": None,
                        "is_resend": True,
                        "size": len(encrypted_packet),
                        "entries": [
                            {
                                "message_number": msg_num,
                                "reliability": reliability,
                                "full_packet": full_packet,
                                "original_payload": data,
                            }
                        ],
                    }
                )

                self.pending_acks[msg_num] = now

    def _pump_network_datagrams(
        self,
        max_datagrams: int = _MAX_RECV_DATAGRAMS_PER_PUMP,
        max_time_sec: float = _MAX_RECV_PUMP_TIME_SEC,
    ) -> int:
        read_count = 0
        started = time.perf_counter()

        while read_count < max_datagrams:
            if time.perf_counter() - started >= max_time_sec:
                break

            if len(self._recv_buffer) >= _RECV_BUFFER_SOFT_LIMIT:
                break

            raw = self.network.recv()

            if not raw:
                break

            read_count += 1

            packets = self.parse_datagram(raw)
            self._recv_buffer.extend(packets)

        return read_count

    def pump_network(self) -> int:
        return self._pump_network_datagrams()

    def recv_and_parse(self) -> dict | None:

        if self._should_flush():
            self._flush_acks()

        if self._recv_buffer:
            return self._recv_buffer.popleft()

        self._pump_network_datagrams()

        if self._recv_buffer:
            return self._recv_buffer.popleft()

        return None

    @staticmethod
    def _raw_packet(data: bytes) -> dict:
        return {
            "type": "raw",
            "message_number": None,
            "reliability": None,
            "data": data,
        }

    def parse_datagram(self, data: bytes) -> list[dict]:

        if not data:
            return []

        packets = []

        if len(data) < 3:
            return [self._raw_packet(data)]


        bs = BitStream(data)

        has_acks = bs.read_bool()


        if has_acks:
            try:
                ranges = self._deserialize_range_list(bs)
            except Exception:
                ranges = []

            for rmin, rmax in ranges:
                for msg_num in range(rmin, rmax + 1):
                    self._remove_pending(msg_num)

        if bs.remaining_bits < 16:
            if has_acks:
                packets.append({"type": "ack", "data": data})
            return packets

        while bs.remaining_bits >= 16:

            if bs.remaining_bits < 24:
                packets.append(self._raw_packet(data[bs.bitpos // 8:]))
                break

            try:
                pkt = self._parse_one_packet(bs)

                
                if pkt.get("checksum_ok") is False:
                    continue

                if self._is_reliable_reliability(pkt.get("reliability")):
                    self._queue_ack(pkt["message_number"])

                self._extend_received_message_number(pkt)
                duplicate = self._is_duplicate_reliable_packet(pkt)

                deliverable = None
                if pkt.get("has_split"):
                    deliverable = self._handle_split_packet(pkt)

                elif not duplicate:
                    deliverable = pkt

                if deliverable is not None:
                    packets.extend(
                        self._apply_delivery_order(deliverable)
                    )

            except Exception:
                packets.append(self._raw_packet(data[bs.bitpos // 8:]))
                break

        return packets

    def _parse_one_packet(self, bs: BitStream) -> dict:
        msg_num = bs.read_uint16()
        reliability = bs.read_bits(3)
        encrypted = self._is_encrypted_reliability(reliability)

        header_checksum = bs.read_uint8() if encrypted else None
        checksum_ok = None
        calculated_checksum = None

        ordering_channel = None
        ordering_index = None

        if self._has_ordering_metadata(reliability):
            ordering_index = bs.read_uint16()
            ordering_channel = (~bs.read_bits(4)) & 0x0F

        has_split = bs.read_bool()
        split_id = None
        split_index = None
        split_count = None

        if has_split:
            split_id = bs.read_uint16()
            split_index = bs.read_compressed(32, unsigned=True)
            split_count = bs.read_compressed(32, unsigned=True)

        bitlen = bs.read_compressed(16, unsigned=True)
        body_bytes = (bitlen + 7) // 8

        bs.align_to_byte()
        encrypted_body = bs.read_bytes(body_bytes) if body_bytes else b""

        if encrypted:
            body, checksum_ok, calculated_checksum = (
                self.security.decode_with_checksum(
                    encrypted_body,
                    header_checksum,
                )
            )
        else:
            body = encrypted_body

        return {
            "type": "packet",
            "message_number": msg_num,
            "reliability": reliability,
            "ordering_channel": ordering_channel,
            "ordering_index": ordering_index,
            "has_ack": False,
            "has_split": has_split,
            "split_id": split_id,
            "split_index": split_index,
            "split_count": split_count,
            "bitlen": bitlen,
            "encrypted": encrypted,
            "header_checksum": header_checksum,
            "calculated_checksum": calculated_checksum,
            "checksum_ok": checksum_ok,
            "encrypted_data": encrypted_body,
            "data": body,
            "reassembled": False,
        }
