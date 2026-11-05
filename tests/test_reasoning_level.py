"""The reasoning level a task asks for reaches the provider (llm_openai.reasoning): DeepSeek's thinking, switched on
alone, runs at its default, high, so the links' "low" asked for it at high (a reader's bill for one article of 182
paragraphs). No network: the fields each request would carry, most fitting first.

Run from the repo root:
    python3 -m unittest discover tests
"""
import unittest

from textfold import llm_openai

DEEPSEEK = "https://api.deepseek.com/v1"


class Levels(unittest.TestCase):
    def test_deepseek_is_asked_for_the_level_itself(self):
        ways = llm_openai.reasoning(DEEPSEEK, "low")
        self.assertEqual(ways[0], {"thinking": {"type": "enabled"}, "reasoning_effort": "low"})
        self.assertIn({"thinking": {"type": "enabled"}}, ways)   # (should a model not take a level)
        self.assertEqual(ways[-1], {})

    def test_deepseek_off_is_off(self):
        self.assertEqual(llm_openai.reasoning(DEEPSEEK, "off")[0], {"thinking": {"type": "disabled"}})

    def test_kimi_as_before(self):
        self.assertEqual(llm_openai.reasoning("https://api.moonshot.cn/v1", "low")[0], {"thinking": {"type": "enabled"}})


if __name__ == "__main__":
    unittest.main()
