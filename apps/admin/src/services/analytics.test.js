import { expect, it } from "vitest";
import { histogram, percent, decimal } from "./analytics";
it("counts finite observations once, including both bin endpoints", () => {
  const bins = histogram([0.2, 0.3, 0.4, 0.4, NaN, Infinity], 4);
  expect(bins.reduce((sum, bin) => sum + bin.count, 0)).toBe(4);
  expect(bins.at(-1).count).toBe(2);
});
it("keeps empty and constant distributions honest", () => {
  expect(histogram([])).toEqual([]);
  expect(
    histogram([0.5, 0.5, 0.5]).reduce((sum, bin) => sum + bin.count, 0),
  ).toBe(3);
});
it("formats measured fractions without inventing missing values", () => {
  expect(percent(0.503916449)).toBe("50.39%");
  expect(percent(undefined)).toBe("—");
  expect(decimal(0.5838056, 6)).toBe("0.583806");
  expect(decimal(NaN)).toBe("—");
});
