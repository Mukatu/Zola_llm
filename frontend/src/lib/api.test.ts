import { describe, it, expect, vi, beforeEach } from "vitest";
import { api, ApiError } from "./api";
import * as auth from "./auth";

// On mocke le module d'auth : api() en dépend pour le jeton, le CSRF, le
// refresh, le repli dev-token, la reconfirmation `me()` et la redirection.
vi.mock("./auth", () => ({
  getToken: vi.fn(),
  getCsrf: vi.fn(),
  refreshSession: vi.fn(),
  fetchDevToken: vi.fn(),
  redirectToLogin: vi.fn(),
  me: vi.fn(),
}));

const mkRes = (status: number, body: unknown = {}) => ({
  status,
  ok: status >= 200 && status < 300,
  json: async () => body,
  text: async () => (typeof body === "string" ? body : JSON.stringify(body)),
});

const USER = { email: "a@b.cg", display_name: "A", tenant_id: "t", country: "cg", role: "admin", scopes: [] };

beforeEach(() => {
  vi.clearAllMocks();
  (auth.getToken as ReturnType<typeof vi.fn>).mockReturnValue(undefined);
  (auth.getCsrf as ReturnType<typeof vi.fn>).mockReturnValue("csrf");
  (auth.refreshSession as ReturnType<typeof vi.fn>).mockResolvedValue(false);
  (auth.fetchDevToken as ReturnType<typeof vi.fn>).mockResolvedValue(null);
  (auth.me as ReturnType<typeof vi.fn>).mockResolvedValue(null);
});

describe("api() — gestion des 401", () => {
  it("chemin nominal : renvoie les données, ne redirige pas", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce(mkRes(200, { ok: 1 }));
    const data = await api<{ ok: number }>("/v1/cortex/psa/alerts");
    expect(data).toEqual({ ok: 1 });
    expect(auth.redirectToLogin).not.toHaveBeenCalled();
  });

  it("401 transitoire mais session encore valide (me() OK) → rejoue, PAS de retour login", async () => {
    // refresh échoue, pas de dev-token, mais /v1/auth/me confirme la session :
    // la requête d'origine est rejouée et réussit — aucun rebond vers /login.
    (auth.me as ReturnType<typeof vi.fn>).mockResolvedValue(USER);
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(mkRes(401))
      .mockResolvedValueOnce(mkRes(200, { ok: 2 }));
    const data = await api<{ ok: number }>("/v1/cortex/psa/alerts");
    expect(data).toEqual({ ok: 2 });
    expect(auth.me).toHaveBeenCalledTimes(1);
    expect(auth.redirectToLogin).not.toHaveBeenCalled();
  });

  it("session réellement morte (me() null) → redirige vers /login et lève 401", async () => {
    (auth.me as ReturnType<typeof vi.fn>).mockResolvedValue(null);
    global.fetch = vi.fn().mockResolvedValue(mkRes(401));
    await expect(api("/v1/cortex/psa/alerts")).rejects.toBeInstanceOf(ApiError);
    expect(auth.redirectToLogin).toHaveBeenCalledTimes(1);
  });

  it("refresh réussit → rejoue sans consulter me() ni rediriger", async () => {
    (auth.refreshSession as ReturnType<typeof vi.fn>).mockResolvedValue(true);
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(mkRes(401))
      .mockResolvedValueOnce(mkRes(200, { ok: 3 }));
    const data = await api<{ ok: number }>("/v1/cortex/psa/alerts");
    expect(data).toEqual({ ok: 3 });
    expect(auth.me).not.toHaveBeenCalled();
    expect(auth.redirectToLogin).not.toHaveBeenCalled();
  });
});
