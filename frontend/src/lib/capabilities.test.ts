import { describe, it, expect } from "vitest";
import { navGroupsFromModules, getCapability, CAPABILITIES } from "./capabilities";

describe("capabilities", () => {
  it("résout une capacité connue et ignore l'inconnue", () => {
    expect(getCapability("erp.paie")?.label).toBe("Paie");
    expect(getCapability("pole.inexistant")).toBeUndefined();
  });

  it("groupe les modules activés par pôle", () => {
    const groups = navGroupsFromModules(["erp.rh", "erp.paie", "bi.pilotage", "pole.inconnu"]);
    const erp = groups.find((g) => g.pole === "erp");
    expect(erp?.items.map((i) => i.code).sort()).toEqual(["erp.paie", "erp.rh"]);
    expect(groups.find((g) => g.pole === "bi")).toBeTruthy();
    // module inconnu ignoré
    expect(groups.some((g) => g.pole === "pole")).toBe(false);
  });

  it("toute capacité a une route /c/<code> et au moins le code en clé", () => {
    for (const [code, cap] of Object.entries(CAPABILITIES)) {
      expect(cap.route).toBe(`/c/${code}`);
      expect(cap.pole).toBe(code.split(".")[0]);
    }
  });
});
