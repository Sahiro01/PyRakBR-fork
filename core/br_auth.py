

_AUTH_SEEDS = [
    0xA311, 0xA436, 0xAF70, 0xA5BD,
    0xAC07, 0xA693, 0xABE2, 0xA119,
    0xAE4B, 0xA7D0, 0xAAC5, 0xA00A,
    0xA2BC, 0xA5D1, 0xA88D, 0xAD62,
    0xA658, 0xA9A3, 0xA46D, 0xAB30,
    0xA081, 0xAC14, 0xA7CB, 0xAEDF,
    0xA326, 0xA133, 0xAF50, 0xA515,
    0xA9E8, 0xA242, 0xA69C, 0xAA67,
]




_AUTH_GLOBAL_XOR = 0xA5C3

_U32_MASK = 0xFFFFFFFF
_MUL_A = (-0x61C8864F) & _U32_MASK
_MUL_B = (-0x3D4D51C3) & _U32_MASK
_CONST_MIX = 0x85EBCA77
_CONST_XOR = 0x5A5A5A5A


def _u32(value: int) -> int:
    return value & _U32_MASK


def _rotr32(value: int, count: int) -> int:
    value &= _U32_MASK
    count &= 31

    if count == 0:
        return value

    return ((value >> count) | (value << (32 - count))) & _U32_MASK


def _auth_mix_finish(value: int, add_value: int) -> int:
    mixed = _u32(value * _MUL_B)

    return _u32((mixed ^ (mixed >> 15)) + add_value)


def _sub_4d368c(key: str) -> str:
    if not isinstance(key, str):
        raise TypeError("auth key must be str")

    key_bytes = key.encode("ascii")
    n = len(key_bytes)

    if n > 0x80:
        
        
        raise ValueError(f"bad len {n}")

    buf = bytearray(0x81)
    buf[:n] = key_bytes
    buf[n] = 0

    state = [
        (_AUTH_GLOBAL_XOR ^ seed) & _U32_MASK
        for seed in _AUTH_SEEDS
    ]

    if n == 0:
        state = [
            v & 0xFFF
            for v in state
        ]

    else:
        local_134 = -0x15B
        local_138 = 0

        for idx in range(0x20):
            u8 = state[idx]
            i14 = 0

            for pos in range(n):
                b = buf[pos]
                u12 = b

                u6 = _u32(pos * -0x4F + u12)
                u3 = _u32(pos + ((u12 + i14) & 0xFF))

                u8 = _u32(u8 + u3)
                u13 = u6 & 0xFF

                u8 = _u32((idx - n) + _rotr32(u8, 25)) ^ u8
                u8 = _u32(
                    ((u13 << 2) ^ _rotr32(u8, 27) ^ 0x20)
                    + local_134
                    + pos
                )
                u8 = _u32(u8 * _MUL_A)

                branch = u12 & 3

                if (b & 3) == 0:
                    r1 = ((~u8) & 0x1F) | 0x18
                    u4 = _u32(local_138 + pos)
                    r2 = ((~u13) & 0x1F) | 0x10

                    t = _u32((u13 | 1) * _MUL_A)
                    t = _u32(t + (_rotr32(u13, r1) ^ u8))
                    t = _u32(t ^ _rotr32(u4, r2))
                    i10 = _u32(t - (u4 ^ _CONST_MIX))

                    u3 = _auth_mix_finish(
                        i10,
                        _rotr32(u8, (-u4) & 0x1F)
                    )

                elif branch == 1:
                    u4 = _u32(u8 ^ pos)
                    r1 = ((~u13) & 0x1F) | 0x18
                    r2 = (-((idx & 0xF) + 1)) & 0x1F

                    t = _u32(
                        (_rotr32(idx, r1) ^ u13)
                        + _u32((idx | 1) * _MUL_A)
                    )
                    t = _u32(t ^ _rotr32(u4, r2))
                    t = _u32(t - (u4 ^ _CONST_MIX))
                    t = _u32(t * _MUL_B)

                    u3 = _u32(
                        _rotr32(u13, (-u4) & 0x1F)
                        + (t ^ (t >> 15))
                    )

                elif branch == 2:
                    r1 = (-((idx & 7) + 1)) & 0x1F
                    r2 = ((~u8) & 0x1F) | 0x10

                    t = _u32((u8 | 1) * _MUL_A)
                    t = _u32(t + (_rotr32(u8, r1) ^ idx))
                    t = _u32(t ^ _rotr32(u3, r2))
                    t = _u32(t - (u3 ^ _CONST_MIX))
                    t = _u32(t * _MUL_B)

                    u3 = _u32(
                        _rotr32(idx, (-u3) & 0x1F)
                        + (t ^ (t >> 15))
                    )

                else:
                    u7 = _u32(u8 ^ u13)
                    u4 = _u32(idx ^ u13)
                    r1 = ((~u7) & 0x1F) | 0x18
                    u9 = _u32(pos ^ idx)
                    r2 = ((~u4) & 0x1F) | 0x10

                    t = _u32((u4 | 1) * _MUL_A)
                    t = _u32(t + (_rotr32(u4, r1) ^ u7))
                    t = _u32(_rotr32(u9, r2) ^ t)
                    i10 = _u32(t - (u9 ^ _CONST_MIX))

                    u3 = _auth_mix_finish(
                        i10,
                        _rotr32(u7, (-u9) & 0x1F)
                    )

                r = (-(u6 & 0xF)) & 0x1F
                u8 = _u32(u8 ^ _rotr32(u3, r))

                check = _u32(u8 ^ u13) | 1

                if ((check * check) & 5) == 1:
                    r1 = ((~u3) & 0x1F) | 0x18
                    r2 = ((~u8) & 0x1F) | 0x10

                    t = _u32((u8 | 1) * _MUL_A)
                    t = _u32(t + (_rotr32(u8, r1) ^ u3))
                    t = _u32(t ^ _rotr32(u13, r2))
                    t = _u32(t - (u13 ^ _CONST_MIX))
                    t = _u32(t * _MUL_B)

                    add = _u32(
                        _rotr32(u3, (-u13) & 0x1F)
                        + (t ^ (t >> 15))
                    )

                    u8 = _u32(u8 + (add ^ _CONST_XOR))

                i14 = _u32(i14 - 0x4F)

                buf[pos] = (
                    b
                    + (((idx & 0xFF) + (n & 0xFF)) & 0xFF) * 4
                ) & 0xFF

            local_138 = _u32(local_138 + 0x1F)
            state[idx] = u8 & 0xFFF
            local_134 -= 1

    out = bytearray(97)

    for i in range(32):
        v = state[i] & 0xFFF
        base = i * 3

        out[base] = ((v >> 8) & 0xF) + 0x44      
        out[base + 1] = ((v >> 4) & 0xF) + 0x47  
        out[base + 2] = (v & 0xF) + 0x4B         

    out[96] = 0

    return out[:96].decode("ascii")


