import { describe, expect, test } from "vitest";
import { foldToolLines, toolResultKeep } from "../extension/tools";

const BASH = ["", " aaa", " bbb", " ccc", " ddd", " eee", " … (3 earlier lines, ctrl+o to expand)", ""];

describe("how many result lines a level keeps", () => {
	test("Full and Brief keep Pi's own row, Points keeps two, Outline and Gist keep none", () => {
		expect([1, 2, 3, 4, 5].map(toolResultKeep)).toEqual([5, 5, 2, 0, 0]);
	});

	test("a level outside 1..5 keeps everything: a corrupt level must not hide output", () => {
		for (const level of [0, 6, 7, 9, 2.5, Number.NaN]) expect(toolResultKeep(level)).toBe(Infinity);
	});
});

describe("folding a tool result", () => {
	test("Full and Brief return the lines as Pi drew them", () => {
		expect(foldToolLines(BASH, 1)).toBe(BASH);
		expect(foldToolLines(BASH, 2)).toBe(BASH);
	});

	test("Points keeps the first two lines of output and names the rest", () => {
		const out = foldToolLines(BASH, 3);
		expect(out).toEqual([" aaa", " bbb", "… (4 more lines · Alt+1)"]);
	});

	test("Outline and Gist keep no result body", () => {
		expect(foldToolLines(BASH, 4)).toEqual([]);
		expect(foldToolLines(BASH, 5)).toEqual([]);
	});

	test("nothing hidden means no marker", () => {
		expect(foldToolLines(["", " aaa", " bbb", ""], 3)).toEqual([" aaa", " bbb"]);
	});

	test("an empty result stays empty", () => {
		expect(foldToolLines([], 3)).toEqual([]);
		expect(foldToolLines(["", "  "], 3)).toEqual([]);
	});

	test("a hidden line count is the non-empty lines the reader cannot see", () => {
		const many = ["x", "y", "z", "w"].map((s) => ` ${s}`);
		expect(foldToolLines(many, 3)[2]).toBe("… (2 more lines · Alt+1)");
	});

	test("anything but 3, 4 and 5 returns the lines as Pi drew them: a corrupt level must not hide output", () => {
		for (const level of [0, 6, 7, 2.5, Number.NaN]) expect(foldToolLines(BASH, level)).toBe(BASH);
	});
});

describe("folding a tool result that is an error", () => {
	const POINTS = [" aaa", " bbb", "… (4 more lines · Alt+1)"];

	test("Outline and Gist keep what Points keeps: a failed step stays visible", () => {
		expect(foldToolLines(BASH, 4, true)).toEqual(POINTS);
		expect(foldToolLines(BASH, 5, true)).toEqual(POINTS);
	});

	test("Points is unchanged, and Full and Brief stay Pi's own row", () => {
		expect(foldToolLines(BASH, 3, true)).toEqual(POINTS);
		expect(foldToolLines(BASH, 1, true)).toBe(BASH);
		expect(foldToolLines(BASH, 2, true)).toBe(BASH);
	});

	test("a level outside 1..5 keeps everything for an error too", () => {
		expect(foldToolLines(BASH, 9, true)).toBe(BASH);
		expect(foldToolLines(BASH, Number.NaN, true)).toBe(BASH);
	});

	test("a short error shows whole, with no marker", () => {
		expect(foldToolLines(["", " exit 1", ""], 5, true)).toEqual([" exit 1"]);
	});
});
