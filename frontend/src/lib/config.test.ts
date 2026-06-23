import { describe, it, expect } from "vitest";
import { hexToRgbTriplet } from "./config";

describe("hexToRgbTriplet", () => {
  it("convertit un hex valide en triplet r g b", () => {
    expect(hexToRgbTriplet("#0B5FFF")).toBe("11 95 255");
    expect(hexToRgbTriplet("00aa55")).toBe("0 170 85");
  });
  it("retombe sur le bleu par défaut si invalide", () => {
    expect(hexToRgbTriplet("nope")).toBe("11 95 255");
  });
});
