# BitStream

Побитовый поток `core/bitstream.py`. Все чтения/записи идут от текущей битовой позиции (`bitpos`), позиция двигается автоматически. Отдельные методы пишут/читают только при выровненной позиции, иначе работают побитово.

## Write

- `write_bit(bit)` - записывает один бит.
  ```python
  bs.write_bit(1)
  ```
- `write_bits(value, count)` - записывает `count` бит значения.
  ```python
  bs.write_bits(5, 3)
  ```
- `write_uint8(value)` - записывает `uint8`.
- `write_uint16(value)` - записывает `uint16`.
- `write_uint32(value)` - записывает `uint32`.
- `write_int8(value)` - записывает `int8`.
- `write_int16(value)` - записывает `int16`.
- `write_int32(value)` - записывает `int32`.
- `write_float(value)` - записывает `float`.
- `write_bool(value)` - записывает `bool`.
- `write_bytes(data)` - записывает `bytes`.
- `write_compressed(value, size, unsigned=True)` - записывает сжатое целое.

## Read

- `read_bit()` - читает один бит.
- `read_bits(count)` - читает `count` бит.
- `read_uint8()` - читает `uint8`.
- `read_uint16()` - читает `uint16`.
- `read_uint32()` - читает `uint32`.
- `read_int8()` - читает `int8`.
- `read_int16()` - читает `int16`.
- `read_int32()` - читает `int32`.
- `read_float()` - читает `float`.
- `read_bool()` - читает `bool`.
- `read_bytes(count)` - читает `count` байт.
- `read_string(...)` - читает строку из потока.
- `read_cstring(...)` - читает null-terminated строку.
- `read_compressed(size, unsigned=True)` - читает сжатое целое.
- `read_compressed_string(...)` - читает сжатую строку.

## Position

- `align_to_byte()` - выравнивает позицию до следующего байта.
- `seek_bits(pos)` - устанавливает битовую позицию.
- `skip_bits(count)` - пропускает указанное количество бит.
- `remaining_bits()` - возвращает количество оставшихся бит.
- `get_bytes()` - возвращает содержимое потока как `bytes`.
- `len(bs)` - возвращает длину потока.
