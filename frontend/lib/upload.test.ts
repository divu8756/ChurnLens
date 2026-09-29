import { describe, expect, it } from "vitest";

import { uploadProblem } from "./upload";

describe("uploadProblem", () => {
  it("accepts csv and xlsx in any case", () => {
    expect(uploadProblem({ name: "data.CSV", size: 10 })).toBeNull();
    expect(uploadProblem({ name: "book.xlsx", size: 10 })).toBeNull();
  });

  it("rejects other types, empty files and files over the limit", () => {
    expect(uploadProblem({ name: "old.xls", size: 10 })).toMatch(/Only \.csv and \.xlsx/);
    expect(uploadProblem({ name: "noext", size: 10 })).toMatch(/Only \.csv and \.xlsx/);
    expect(uploadProblem({ name: "a.csv", size: 0 })).toBe("The file is empty.");
    expect(uploadProblem({ name: "a.csv", size: 2 * 1024 * 1024 + 1 }, 2)).toMatch(/larger than 2 MB/);
    expect(uploadProblem({ name: "a.csv", size: 2 * 1024 * 1024 }, 2)).toBeNull();
  });
});
