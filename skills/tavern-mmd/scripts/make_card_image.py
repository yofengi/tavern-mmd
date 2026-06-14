#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tavern-mmd 角色卡图片导出 make_card_image.py

把角色卡 JSON 嵌入图片，产出可导入的 png（默认）/ jpg（按需，实验性）。
纯 Python 标准库，无 pip 依赖。

用法:
  python make_card_image.py <卡JSON> [--format png|jpg] [--bg 底图路径] [-o 输出路径]
"""
import sys
import os
import zlib
import struct
import base64
import json
import argparse

PNG_SIG = b"\x89PNG\r\n\x1a\n"

BG_W, BG_H = 512, 768
BG_RGB = (0xF5, 0xEB, 0xDC)   # 米黄
TEXT_RGB = (0xB8, 0xA9, 0x8C) # 米褐，比底色略深

# 5×7 点阵字体，覆盖标签所需字符（小写字母 + - . /）
FONT = {
    "a": [".....", ".....", ".###.", "....#", ".####", "#...#", ".####"],
    "b": ["#....", "#....", "####.", "#...#", "#...#", "#...#", "####."],
    "c": [".....", ".....", ".###.", "#....", "#....", "#....", ".###."],
    "d": ["....#", "....#", ".####", "#...#", "#...#", "#...#", ".####"],
    "e": [".....", ".....", ".###.", "#...#", "#####", "#....", ".###."],
    "f": ["..##.", ".#...", ".#...", "####.", ".#...", ".#...", ".#..."],
    "g": [".....", ".####", "#...#", "#...#", ".####", "....#", ".###."],
    "h": ["#....", "#....", "####.", "#...#", "#...#", "#...#", "#...#"],
    "i": ["..#..", ".....", ".##..", "..#..", "..#..", "..#..", ".###."],
    "m": [".....", ".....", "##.#.", "#.#.#", "#.#.#", "#.#.#", "#.#.#"],
    "n": [".....", ".....", "####.", "#...#", "#...#", "#...#", "#...#"],
    "o": [".....", ".....", ".###.", "#...#", "#...#", "#...#", ".###."],
    "r": [".....", ".....", "#.##.", "##..#", "#....", "#....", "#...."],
    "t": [".#...", ".#...", "####.", ".#...", ".#...", ".#..#", "..##."],
    "u": [".....", ".....", "#...#", "#...#", "#...#", "#...#", ".####"],
    "v": [".....", ".....", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "y": [".....", ".....", "#...#", "#...#", ".####", "....#", ".###."],
    "-": [".....", ".....", ".....", "#####", ".....", ".....", "....."],
    ".": [".....", ".....", ".....", ".....", ".....", ".##..", ".##.."],
    "/": ["....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."],
}
LINE1 = "tavern-mmd"
LINE2 = "github.com/yofengi/tavern-mmd"


def png_chunk(ctype, data):
    """组装一个 PNG chunk: 长度(4) + 类型(4) + 数据 + CRC32(4)。"""
    return (struct.pack(">I", len(data)) + ctype + data
            + struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF))


def buffer_to_png(buf, w, h):
    """把 RGB 像素缓冲(bytearray, 每像素3字节)编码为 PNG bytes。"""
    raw = bytearray()
    for y in range(h):
        raw.append(0)  # 每行 filter 字节 = 0 (None)
        raw.extend(buf[y * w * 3:(y + 1) * w * 3])
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)  # 8bit, color type 2 = RGB
    idat = zlib.compress(bytes(raw), 9)
    return (PNG_SIG + png_chunk(b"IHDR", ihdr)
            + png_chunk(b"IDAT", idat) + png_chunk(b"IEND", b""))


def read_all_chunks(png):
    """解析 PNG，返回 [(type_bytes, data_bytes), ...]。"""
    assert png.startswith(PNG_SIG), "不是合法 PNG"
    out = []
    i = len(PNG_SIG)
    while i < len(png):
        (length,) = struct.unpack(">I", png[i:i + 4])
        ctype = png[i + 4:i + 8]
        data = png[i + 8:i + 8 + length]
        out.append((ctype, data))
        i += 12 + length
    return out


def _text_chunk(keyword, text):
    """tEXt chunk: keyword + \x00 + text(latin-1 安全的 base64 ASCII)。"""
    return png_chunk(b"tEXt", keyword + b"\x00" + text.encode("latin-1"))


def inject_text_chunks(png, json_str, is_v3):
    """在第一个 IDAT 前插入 chara(=base64 JSON) tEXt；v3 额外插入 ccv3。
    会先剥除已有的 chara/ccv3 tEXt，避免重复。"""
    b64 = base64.b64encode(json_str.encode("utf-8")).decode("ascii")
    chunks = read_all_chunks(png)
    out = bytearray(PNG_SIG)
    inserted = False
    for ctype, data in chunks:
        if ctype == b"tEXt" and data.split(b"\x00", 1)[0] in (b"chara", b"ccv3"):
            continue  # 丢弃旧的角色卡 chunk
        if ctype == b"IDAT" and not inserted:
            out += _text_chunk(b"chara", b64)
            if is_v3:
                out += _text_chunk(b"ccv3", b64)
            inserted = True
        out += png_chunk(ctype, data)
    return bytes(out)


def read_keyword(png, keyword):
    """读回指定 keyword 的 tEXt 文本并 base64 解码为 UTF-8 字符串；无则 None。"""
    for ctype, data in read_all_chunks(png):
        if ctype == b"tEXt":
            kw, _, text = data.partition(b"\x00")
            if kw == keyword:
                return base64.b64decode(text).decode("utf-8")
    return None


def read_chara(png):
    """读回 chara chunk 的 JSON 字符串。"""
    return read_keyword(png, b"chara")


def _set_px(buf, x, y, rgb):
    if 0 <= x < BG_W and 0 <= y < BG_H:
        i = (y * BG_W + x) * 3
        buf[i], buf[i + 1], buf[i + 2] = rgb


def _text_width(text, scale):
    return len(text) * 6 * scale  # 5px 字宽 + 1px 间隔


def _draw_text(buf, x, y, text, scale, rgb):
    for ch in text:
        glyph = FONT.get(ch)
        if glyph:
            for row in range(7):
                for col in range(5):
                    if glyph[row][col] == "#":
                        for dy in range(scale):
                            for dx in range(scale):
                                _set_px(buf, x + col * scale + dx,
                                        y + row * scale + dy, rgb)
        x += 6 * scale


def make_default_buffer():
    """生成默认米黄底图的 RGB 缓冲，下部居中画两行标签。"""
    buf = bytearray(BG_RGB * (BG_W * BG_H))
    s1, s2 = 5, 2
    y1 = int(BG_H * 0.70)
    y2 = y1 + 7 * s1 + 12
    _draw_text(buf, (BG_W - _text_width(LINE1, s1)) // 2, y1, LINE1, s1, TEXT_RGB)
    _draw_text(buf, (BG_W - _text_width(LINE2, s2)) // 2, y2, LINE2, s2, TEXT_RGB)
    return buf


def make_default_bg():
    return buffer_to_png(make_default_buffer(), BG_W, BG_H)


def embed_png(png_bytes, json_str, is_v3):
    """把卡 JSON 嵌入一张已有 PNG（剥除旧 chara/ccv3 后注入）。"""
    if not png_bytes.startswith(PNG_SIG):
        raise ValueError("--bg 为 png 格式时文件必须是合法 PNG")
    return inject_text_chunks(png_bytes, json_str, is_v3)


def embed_jpg(jpg_bytes, json_str):
    """在 JPEG SOI 后插入 COM 段携带 chara base64。实验性，未在 MMD 实机验证。"""
    if not jpg_bytes.startswith(b"\xff\xd8"):
        raise ValueError("--bg 为 jpg 格式时文件必须是合法 JPEG（以 FFD8 开头）")
    payload = b"chara\x00" + base64.b64encode(json_str.encode("utf-8"))
    seg_len = len(payload) + 2  # COM 段长度含长度字段自身的 2 字节
    if seg_len > 0xFFFF:
        raise ValueError("卡 JSON 过大，超出单个 COM 段上限")
    com = b"\xff\xfe" + struct.pack(">H", seg_len) + payload
    return jpg_bytes[:2] + com + jpg_bytes[2:]


def read_jpg_chara(jpg_bytes):
    """从 JPEG 的 COM 段读回 chara JSON 字符串；无则 None。"""
    i = 2
    while i + 4 <= len(jpg_bytes):
        if jpg_bytes[i] != 0xFF:
            break
        marker = jpg_bytes[i + 1]
        if marker in (0xD8, 0xD9):  # SOI/EOI 无长度字段
            i += 2
            continue
        (seg_len,) = struct.unpack(">H", jpg_bytes[i + 2:i + 4])
        seg = jpg_bytes[i + 4:i + 2 + seg_len]
        if marker == 0xFE and seg.startswith(b"chara\x00"):
            return base64.b64decode(seg[6:]).decode("utf-8")
        i += 2 + seg_len
    return None


def _load_card(path):
    with open(path, "rb") as f:
        raw = f.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("卡 JSON 含 UTF-8 BOM，请去除后再嵌入")
    card = json.loads(raw.decode("utf-8"))
    spec = card.get("spec", "")
    is_v3 = (spec == "chara_card_v3")
    return raw.decode("utf-8"), is_v3


def main(argv=None):
    p = argparse.ArgumentParser(description="把角色卡 JSON 嵌入图片导出")
    p.add_argument("card", help="角色卡 JSON 文件路径")
    p.add_argument("--format", choices=["png", "jpg"], default="png")
    p.add_argument("--bg", help="底图路径；png 省略则生成默认米黄底图；jpg 必填")
    p.add_argument("-o", "--output", help="输出路径（默认与卡同名换扩展名）")
    a = p.parse_args(argv)

    try:
        json_str, is_v3 = _load_card(a.card)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        sys.stderr.write("卡 JSON 读取失败: %s\n" % e)
        return 1

    try:
        if a.format == "png":
            if a.bg:
                with open(a.bg, "rb") as f:
                    out_bytes = embed_png(f.read(), json_str, is_v3)
            else:
                out_bytes = embed_png(make_default_bg(), json_str, is_v3)
        else:  # jpg
            sys.stderr.write(
                "[待验证] JPG 嵌入未在 MMD 实机验证，建议优先 PNG。\n")
            if not a.bg:
                sys.stderr.write(
                    "jpg 格式必须用 --bg 提供一张 jpg 底图"
                    "（stdlib 无法从零编码 JPEG）。\n")
                return 1
            with open(a.bg, "rb") as f:
                out_bytes = embed_jpg(f.read(), json_str)
    except (OSError, ValueError) as e:
        sys.stderr.write("嵌入失败: %s\n" % e)
        return 1

    out_path = a.output or (os.path.splitext(a.card)[0] + "." + a.format)
    with open(out_path, "wb") as f:
        f.write(out_bytes)
    sys.stdout.write("已生成 %s\n" % out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
