"""The argument links of a text too long for one call (#91: 2,290 units in one prompt, a reply cut off mid-answer).

A text that fits one call is asked as it always was: one prompt, its wording unchanged, so the reply cached for it is
read again. A longer one is asked in parts, each shown the abstract too, and the parts merge in reading order: a link
once, at most MAX_FROM from a unit. A part that fails costs its own links, no others. A model stands in for one, a data
folder of its own; no network.

Run from the repo root:
    python3 -m unittest discover tests
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from textfold import links, llm, local, pipeline, store

SPEC = {"id": "fake/model", "kind": "api", "protocol": "openai", "base": "http://127.0.0.1:9", "api_key": "", "model": "fake"}
SHORT = """# Heat pump diary

What the house did in the cold week.

## Monday

The heat pump ran all night. Its COP stayed above three, even at minus five.

## Tuesday

A cold front arrived early. The buffer tank emptied by noon and the backup heater started.
"""
# more units than one links call holds: 22 sections of 20 paragraphs
LONG = "# Heat pump diary\n\nWhat the house did.\n\n" + "\n\n".join(
    f"## Day {s}\n\n" + "\n\n".join(f"Paragraph {k} of day {s} says the heat pump ran all night and the tank held." for k in range(20))
    for s in range(22))


def asked_numbers(prompt):
    """The U numbers a prompt lists, in the order it lists them."""
    return [int(w[1:]) for w in prompt.split() if w.startswith("U") and w[1:].isdigit()]


def ladder_reply(prompt):
    n = prompt.count("\n[U")
    return {"section": {"takeaway": "The section in brief", "topic": "The section"},
            "units": [{"id": f"U{k}", "role": "context", "takeaway": f"Point {k}", "topic": "Point",
                       "reason": "", "evidence": [0]} for k in range(n)]}, 0


def model(prompts, links_of=None, fail=None):
    """A section's levels as a model gives them; the links answered by links_of(prompt), or failed when fail says so.
    With no links_of, one link from a prompt's first unit to the one five units on: each part then shows one of its own."""
    def once(prompt, schema, spec, timeout, system):
        prompts.append(prompt)
        if "Its units in reading order" in prompt:
            return ladder_reply(prompt)
        if fail and fail(prompt):
            raise RuntimeError("the reply's JSON does not parse")
        if links_of:
            return {"links": links_of(prompt)}, 0
        first = asked_numbers(prompt)[0]
        return {"links": [{"from": f"U{first}", "to": f"U{first + 5}", "rel": "supports"}]}, 0
    return once


def link_prompts(prompts):
    """The links calls, in reading order (the parts are asked together: in the order they were asked, any)."""
    return sorted((p for p in prompts if "Find the argument links" in p), key=lambda p: asked_numbers(p)[0])


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patch = mock.patch.object(store, "DATA", Path(tmp.name))
        patch.start()
        self.addCleanup(patch.stop)

    def generate(self, text, **kw):
        pid = local.import_text(text, "diary.md")
        asked, said = [], []
        with mock.patch.object(llm, "_once", model(asked, **kw)), mock.patch.dict(os.environ):
            os.environ.pop("TEXTFOLD_NO_MODELS", None)   # (the tests run with it: the model here is a stand-in)
            pipeline.generate(pid, "en", SPEC, log=said.append)
        return pid, asked, said

    def edges(self, pid):
        doc = store.assemble(pid)
        order = [uid for c in doc["chunks"] for uid in c["units"]]
        return doc, order, [e for e in doc["edges"] if e.get("tk") == "unit"]


class OneCall(Base):
    def test_a_text_that_fits_one_call_is_asked_as_it_was(self):
        _, asked, _ = self.generate(SHORT)
        calls = link_prompts(asked)
        self.assertEqual(len(calls), 1)
        self.assertIn("Every unit of the text (paragraph, list item, or figure or table caption) as a one-line takeaway, "
                      "in reading order, with its section and role:", calls[0])
        self.assertIn("about 20 links in total", calls[0])
        self.assertNotIn("This part of the text", calls[0])


class Parts(Base):
    def test_a_long_text_is_asked_in_parts_that_merge_in_reading_order(self):
        pid, asked, _ = self.generate(LONG)
        calls = link_prompts(asked)
        self.assertGreater(len(calls), 1)   # (one prompt could not be answered whole: #91)
        for p in calls:
            self.assertLessEqual(len(asked_numbers(p)), links.MAX_UNITS + links.ABSTRACT_UNITS)
        _, order, edges = self.edges(pid)
        # each part's own link, from its first unit to one five units on, is kept: nothing was lost between the parts
        got = {(order.index(e["f"]), order.index(e["t"])) for e in edges}
        for p in calls:
            first = asked_numbers(p)[0]
            self.assertIn((first, first + 5), got)
        self.assertEqual(len(edges), len(calls))   # a link once

    def test_every_part_after_the_first_is_shown_the_abstract(self):
        _, asked, _ = self.generate(LONG)
        calls = link_prompts(asked)
        self.assertNotIn("\n\nThe abstract is given too", calls[0])   # (the one that holds it has it already)
        for p in calls[1:]:
            self.assertIn("\n\nThe abstract is given too", p)
            self.assertIn("\nU0 ", p)   # its claim, for the evidence a far section gives

    def test_a_unit_keeps_at_most_MAX_FROM_links_across_parts(self):
        # both parts offer links from U0 (the abstract's first unit): the merged reading keeps three of them
        def of(prompt):
            return [{"from": "U0", "to": f"U{n}", "rel": "supports"} for n in asked_numbers(prompt)[1:7]]
        pid, asked, _ = self.generate(LONG, links_of=of)
        _, order, edges = self.edges(pid)
        self.assertGreater(len(link_prompts(asked)), 1)
        self.assertEqual(len([e for e in edges if e["f"] == order[0]]), links.MAX_FROM)

    def test_a_part_keeps_only_links_between_units_it_was_shown(self):
        # each part names a unit fifty before its first (the numbers are the whole text's: in the part before, unseen
        # here) and the abstract's first: the first is dropped, the second kept
        def of(prompt):
            first = asked_numbers(prompt)[0]
            return [{"from": f"U{first + 2}", "to": f"U{max(30, first - 50)}", "rel": "supports"},
                    {"from": f"U{first + 3}", "to": "U0", "rel": "supports"}]
        pid, asked, _ = self.generate(LONG, links_of=of)
        firsts = [asked_numbers(p)[0] for p in link_prompts(asked)]
        _, order, edges = self.edges(pid)
        self.assertGreater(len(firsts), 1)
        self.assertEqual({(order.index(e["f"]), order.index(e["t"])) for e in edges}, {(2, 30)} | {(n + 3, 0) for n in firsts})

    def test_a_part_that_fails_costs_only_its_own_links(self):
        # the second part fails (it is the one the abstract is given to): the first part's links are kept
        pid, asked, said = self.generate(LONG, fail=lambda p: "\n\nThe abstract is given too" in p,
                                         links_of=lambda p: [{"from": f"U{asked_numbers(p)[0]}",
                                                              "to": f"U{asked_numbers(p)[0] + 5}", "rel": "supports"}])
        calls = link_prompts(asked)
        self.assertGreater(len(calls), 1)
        self.assertTrue(any(line.startswith("  ! links part") for line in said))
        self.assertIsNotNone(store.read(pid, "en"))   # the levels are stored
        _, order, edges = self.edges(pid)
        self.assertEqual([order.index(e["f"]) for e in edges], [asked_numbers(calls[0])[0]])   # the first part's only


if __name__ == "__main__":
    unittest.main()
