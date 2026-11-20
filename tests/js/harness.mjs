// Loads game.js, unmodified, into an isolated node:vm context.
//
// document/localStorage/fetch are stubs. fetch returns a promise that never
// settles, so the init() call at the bottom of game.js stays inert. Date is a
// subclass whose no-argument constructor and Date.now() return a settable
// instant, so day-dependent logic is deterministic.
import vm from "node:vm";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const GAME_JS = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
  "game.js",
);

export function loadGame({ now = "2025-01-01T12:00:00Z" } = {}) {
  let current = new Date(now).getTime();

  class FakeDate extends Date {
    constructor(...args) {
      if (args.length === 0) super(current);
      else super(...args);
    }
    static now() {
      return current;
    }
  }

  const store = new Map();
  const localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => void store.set(k, String(v)),
    removeItem: (k) => void store.delete(k),
    clear: () => store.clear(),
  };

  const element = () =>
    new Proxy(function () {}, {
      get: (_t, prop) => (prop === "style" || prop === "classList" ? element() : element()),
      set: () => true,
      apply: () => element(),
    });
  const document = {
    getElementById: element,
    createElement: element,
    importNode: element,
    addEventListener() {},
  };

  const warnings = [];
  const sandbox = {
    document,
    localStorage,
    fetch: () => new Promise(() => {}),
    Date: FakeDate,
    console: { ...console, warn: (...a) => warnings.push(a.join(" ")) },
    AbortController,
    setTimeout,
    clearTimeout,
  };
  const ctx = vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(GAME_JS, "utf8"), ctx, { filename: GAME_JS });

  // Top-level let/const/class are not context properties; reach them (and
  // call functions) by evaluating code in the same context.
  const run = (code) => vm.runInContext(code, ctx);

  return {
    ctx,
    run,
    store,
    warnings,
    setNow(iso) {
      current = new Date(iso).getTime();
    },
    // Replace the game's data tables.
    setData({ munis = [], countyAdj = {}, schedule = null } = {}) {
      ctx.__munis = munis;
      ctx.__adj = countyAdj;
      ctx.__sched = schedule;
      run(`
        MUNIS = __munis; COUNTY_ADJ = __adj; SCHEDULE = __sched;
        MUNI_BY_ID = new Map(MUNIS.map((m) => [m.id, m]));
      `);
    },
  };
}
