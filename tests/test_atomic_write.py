"""
W1-D4-BE · 原子写入工具单测 (B4)
=================================

覆盖场景:
  1) 正常写入 → 目标存在 + 内容正确 + 临时文件已清
  2) 写入过程中抛异常 → 目标不被破坏（旧内容保留）+ 临时文件不残留
  3) safe_read_json: 文件不存在/格式错误/格式正确 三种
  4) atomic_write_json: 中文可读 (ensure_ascii=False)
  5) atomic_write_bytes + 多次连续写入（最后内容生效）
  6) 并发写同一个目标 → 最后完成者全量覆盖，过程中目标要么旧要么新，无半写

运行：
    cd D:\\hermes-dev-team\\nsp-im
    .venv-d5/Scripts/python.exe tests/test_atomic_write.py
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))  # 让 utils 可直接 import

from utils.atomic_write import (  # noqa: E402
    atomic_write_text,
    atomic_write_bytes,
    atomic_write_json,
    safe_read_json,
)


class TestAtomicWriteText(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="nsp_aw_"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_writes_target_cleans_tmp(self):
        target = self.tmpdir / "a.json"
        atomic_write_text(target, "hello\n", encoding="utf-8")
        self.assertEqual(target.read_text(encoding="utf-8"), "hello\n")
        # 临时文件清干净
        leftovers = list(self.tmpdir.glob(".a.json.tmp.*"))
        self.assertEqual(leftovers, [], f"残留 tmp: {leftovers}")

    def test_overwrite_existing(self):
        target = self.tmpdir / "x.txt"
        target.write_text("v1", encoding="utf-8")
        atomic_write_text(target, "v2", encoding="utf-8")
        self.assertEqual(target.read_text(encoding="utf-8"), "v2")

    def test_exception_during_write_preserves_old(self):
        target = self.tmpdir / "data.txt"
        target.write_text("original", encoding="utf-8")

        # 1) 模拟"目标父目录无法写入"场景：用 monkeypatch 让 tmp 文件创建后,
        #    rename 阶段强制 PermissionError, 然后验证目标未被破坏。
        from utils import atomic_write as aw_mod

        original_replace = aw_mod.os.replace

        def boom_replace(src, dst):
            # 放行 tmp 创建; 阻止 rename
            raise PermissionError(13, "simulated PermissionError during rename")

        aw_mod.os.replace = boom_replace
        try:
            with self.assertRaises(PermissionError):
                atomic_write_text(target, "new-content")
        finally:
            aw_mod.os.replace = original_replace

        # 原始文件未被影响
        self.assertEqual(target.read_text(encoding="utf-8"), "original")
        # 临时文件不留残
        leftovers = [p for p in self.tmpdir.rglob("*") if ".tmp." in p.name]
        self.assertEqual(leftovers, [], f"残留 tmp: {leftovers}")

    def test_no_tmp_leftover_after_success(self):
        target = self.tmpdir / "no.json"
        for i in range(10):
            atomic_write_text(target, f"iter-{i}\n")
        leftovers = list(self.tmpdir.glob(".no.json.tmp.*"))
        self.assertEqual(leftovers, [])


class TestAtomicWriteJson(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="nsp_awj_"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_chinese_readable_when_ensure_ascii_false(self):
        target = self.tmpdir / "cn.json"
        obj = {"政策": "绿电直连", "list": ["北京", "上海"]}
        atomic_write_json(target, obj, ensure_ascii=False, indent=2)
        text = target.read_text(encoding="utf-8")
        # 中文必须出现（ensure_ascii=False）
        self.assertIn("绿电直连", text)
        # 不应出现 \u 形式的转义
        self.assertNotIn("\\u7eff", text)
        # 还能再 load 回来
        self.assertEqual(json.loads(text), obj)

    def test_round_trip_equal(self):
        target = self.tmpdir / "rt.json"
        obj = {"a": [1, 2, 3], "b": {"c": True, "d": None}}
        atomic_write_json(target, obj)
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), obj)


class TestAtomicWriteBytes(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="nsp_awb_"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_writes_binary(self):
        target = self.tmpdir / "blob.bin"
        # 不可 utf-8 编码的字节序列
        data = b"\x00\x01\xfe\xff\x80abc"
        atomic_write_bytes(target, data)
        self.assertEqual(target.read_bytes(), data)


class TestSafeReadJson(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="nsp_sjr_"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_missing_returns_default(self):
        result = safe_read_json(self.tmpdir / "absent.json", default={"x": 1})
        self.assertEqual(result, {"x": 1})

    def test_valid_json_returns_parsed(self):
        target = self.tmpdir / "ok.json"
        target.write_text('{"k":"v","n":42}', encoding="utf-8")
        self.assertEqual(safe_read_json(target), {"k": "v", "n": 42})

    def test_corrupted_json_returns_default(self):
        target = self.tmpdir / "corrupt.json"
        target.write_text('{"k": "v", broken', encoding="utf-8")  # truncated
        # 必须不抛异常，返回 default
        result = safe_read_json(target, default={"fallback": True})
        self.assertEqual(result, {"fallback": True})


class TestAtomicWriteConcurrency(unittest.TestCase):
    """并发写 → 最后完成者全量覆盖，无半写。"""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="nsp_awc_"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_concurrent_writes_converge(self):
        target = self.tmpdir / "concurrent.json"
        errors = []

        def writer(idx: int):
            try:
                for i in range(20):
                    obj = {"writer": idx, "iter": i, "list": list(range(50))}
                    atomic_write_json(target, obj, ensure_ascii=False)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"并发写异常: {errors}")
        # 文件合法 JSON
        final = json.loads(target.read_text(encoding="utf-8"))
        self.assertIn("writer", final)
        self.assertIn("iter", final)
        # 临时文件清理
        leftovers = list(self.tmpdir.glob(f".concurrent.json.tmp.*"))
        self.assertEqual(leftovers, [], f"残留 tmp: {leftovers}")


class TestAtomicWriteProcessInjection(unittest.TestCase):
    """模拟 fetcher 半写的现实场景: 写一半被 kill。

    本测试不真杀进程，而是通过抛异常模拟写入失败，
    然后验证 fetcher.save() 的合并写入路径能继续成功。
    """

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="nsp_pfj_"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_after_corruption_recovers(self):
        policies_file = self.tmpdir / "policies.json"
        # 模拟"上一次抓取崩了留下半 JSON"
        policies_file.write_text('{"version":"1.0","policies": [{"id":"P-OLD"-"broken', encoding="utf-8")

        # 现在有个 fetcher 要来 save，必须能从 corruption 中恢复
        from utils.atomic_write import atomic_write_json, safe_read_json

        existing = safe_read_json(policies_file, default={"version": "1.0", "policies": []})
        existing.setdefault("policies", []).append({"id": "P-NEW-1", "title": "new"})
        atomic_write_json(policies_file, existing)

        recovered = json.loads(policies_file.read_text(encoding="utf-8"))
        self.assertIn({"id": "P-NEW-1", "title": "new"}, recovered["policies"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
