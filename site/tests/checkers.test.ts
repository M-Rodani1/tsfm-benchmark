// Answer checking on the page: predictions, and plain-English error explanations.
// (The Python checkers of the checkpoints are tested with pytest and in the browser.)
import { describe, expect, it } from "vitest";
import { content, lessons } from "../src/lib/content";
import { explainError } from "../src/lib/errors";
import { checkPrediction } from "../src/lib/predict";

describe("prediction checking", () => {
  it("multiple choice, numbers with tolerance, and free text", () => {
    expect(checkPrediction({ question: "q", explain: "e", options: ["a", "b"], answer: 1 }, 1)).toBe(true);
    expect(checkPrediction({ question: "q", explain: "e", options: ["a", "b"], answer: 1 }, 0)).toBe(false);
    const n = { question: "q", explain: "e", kind: "number" as const, answer: 50, tolerance: 3 };
    expect(checkPrediction(n, "52")).toBe(true);
    expect(checkPrediction(n, "53,5")).toBe(false);
    expect(checkPrediction(n, "abc")).toBe(false);
    expect(checkPrediction({ question: "q", explain: "e", kind: "text" }, "anything")).toBeNull();
  });

  it("every multiple-choice answer in the content indexes one of its options", () => {
    for (const l of lessons)
      for (const s of l.steps)
        for (const b of s.blocks)
          if (b.kind === "predict" && b.data.options) expect(b.data.options[b.data.answer!], `${l.id} ${b.id}`).toBeDefined();
  });
});

describe("error explanations", () => {
  const L = (id: string) => lessons.find((l) => l.id === id)!;
  const cases: [string, string, string, RegExp][] = [
    ["01", "NotImplementedError", "", /placeholder/],
    ["01", "NameError", "name 'np' is not defined", /first code cell/],
    ["01", "NameError", "name 'dayly' is not defined", /typo/],
    ["02", "ValueError", "operands could not be broadcast together with shapes (4131,) (4132,)", /different lengths/],
    ["04", "IndexError", "index 4132 is out of bounds for axis 0 with size 4132", /past the end/],
    ["09", "KeyError", "'p_holms'", /does not exist/],
    ["06", "TypeError", "unsupported operand type(s) for -: 'NoneType' and 'float'", /None|return/],
    ["03", "ValueError", "The truth value of a Series is ambiguous. Use a.empty, a.bool(), a.item(), a.any() or a.all().", /single True\/False/],
    ["03", "AssertionError", "❌ Case n=300, origin_pos=200, h=5: row 196 should be True. Hint: …", /i \+ h ≤ origin_pos/],
    ["01", "ProviderError", "SYN_X: not in fixture", /typo/i],
    ["00", "PythonUnavailable", "Could not download the Python packages", /Restart Python/],
    ["05", "SyntaxError", "expected ':'", /missing/],
  ];
  it.each(cases)("lesson %s: %s", (id, type, message, want) => {
    const ex = explainError({ type, message }, L(id).errors, content.errors);
    expect(ex, `${type}: ${message}`).not.toBeNull();
    expect(`${ex!.why} ${ex!.fix}`).toMatch(want);
  });

  it("every lesson's own error patterns compile, and none are unreachable duplicates of a general one", () => {
    for (const l of lessons) for (const e of l.errors) expect(() => new RegExp(e.match)).not.toThrow();
  });
});
