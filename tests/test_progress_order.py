"""A generation's progress counts each reply as it comes (reported, from TextFold Bridge in Obsidian: "ladder 0/14" for
minutes). The sections were taken back in the order they were asked, so one slow call first in line held the count at 0
while the others were in; and nothing said a model was slow or silent. Now each section is counted and folded as its
reply comes, and while none comes the job's log says how many are still out and with which model; a translation's
parts are counted as they come and read in the paper's order, so what they bring (the paper's title) does not change
with which came first (as #70 has it). A model that stands
in for one, a data folder of its own; no network.

Run from the repo root:
    python3 -m unittest discover tests
"""
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

import re

from textfold import ladder, llm, local, store, translate

TEXT = """# Notes on folding

## Introduction

Readers skim long papers. They miss the argument.

## Method

We fold each paragraph into a takeaway. The takeaway is one line.

## Results

Readers found the argument sooner.
"""
CFG = {"kind": "api", "id": "fake/slow-first", "effort": "none"}


class Answered(unittest.TestCase):
    def test_as_each_comes_back(self):
        def fn(x):
            time.sleep({"a": 0.3, "b": 0.0, "c": 0.1}[x])
            return x
        with ThreadPoolExecutor(3) as ex:
            self.assertEqual(list(llm.as_answered(ex, fn, ["a", "b", "c"])), ["b", "c", "a"])

    def test_a_silence_said_in_the_log(self):
        said = []
        with mock.patch.object(llm, "WAIT_NOTE", 0.05), ThreadPoolExecutor(2) as ex:
            got = list(llm.as_answered(ex, lambda x: time.sleep(0.2) or x, [1, 2], said.append, "fake/slow"))
        self.assertEqual(sorted(got), [1, 2])
        self.assertTrue(said)
        self.assertIn("2 of 2 still asked of fake/slow", said[0])


class Ladder(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        p = mock.patch.object(store, "DATA", self.tmp / "data")
        p.start()
        self.addCleanup(p.stop)
        self.doc = store.assemble(local.import_text(TEXT))

    def test_counted_while_the_first_is_still_out(self):
        counted = threading.Event()
        seen = []

        def progress(done, total):
            seen.append((done, total, first_back.is_set()))
            if done >= 1:
                counted.set()
        first_back = threading.Event()

        def model(prompt, schema, cfg, cache_dir, force=False, timeout=900, system=None):
            if "Readers skim" in prompt:   # (the first section: back only once another one is counted)
                counted.wait(5)
                first_back.set()
            return {"out": {"units": []}, "cost": 0}, False
        with mock.patch.object(llm, "call", model):
            ladder.build(self.doc, CFG, self.tmp / "cache", jobs=3, log=lambda *a: None, progress=progress)
        total = len([c for c in self.doc["chunks"] if c["units"]])
        self.assertEqual(seen[0], (0, total, False))
        self.assertIn((1, total, False), seen)   # (counted before the first section's reply was in)
        self.assertEqual(seen[-1][:2], (total, total))
        self.assertTrue(all("lad" in u for u in self.doc["units"].values()))


    def test_a_translation_counted_as_it_comes_and_read_in_order(self):
        counted, seen = threading.Event(), []

        def model(prompt, schema, cfg, cache_dir, force=False, timeout=900, system=None):
            if "titles" in schema["properties"]:
                return {"out": {"titles": []}, "cost": 0}, False
            sec = re.sub(r"^[\d.]+\s+", "", re.search(r"^This section: (.*)$", prompt, re.M).group(1))
            if sec == "Introduction":   # (the first part: back only once another one is counted)
                counted.wait(5)
            return {"out": {"section": {"title": f"节：{sec}", "takeaway": "要点", "topic": "要点"}, "units": [],
                            "paper_title": f"标题来自 {sec}"}, "cost": 0}, False

        def progress(done, total):
            seen.append(done)
            if done >= 1:
                counted.set()
        with mock.patch.object(llm, "call", model):
            translate.build(self.doc, "zh", CFG, self.tmp / "cache", jobs=3, log=lambda *a: None, progress=progress)
        self.assertTrue(counted.is_set())
        self.assertEqual(self.doc["meta"]["titles"]["zh"], "标题来自 Results")   # (the paper's order: its last section's)


if __name__ == "__main__":
    unittest.main()
